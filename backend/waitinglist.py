class priority_queue:
    def __init__(self):
        self.heap = []
        self.entry_count = 0  # Tie-breaker for identical timestamps
    
    def heapify_up(self, index):
        parent = (index - 1) // 2  # getting the index value of parent
        while index > 0 and self.heap[index] < self.heap[parent]:
            self.heap[index], self.heap[parent] = self.heap[parent], self.heap[index]
            index = parent
            parent = (index - 1) // 2
    
    def heapify_down(self, idx):
        n = len(self.heap)
        while True:
            left = 2 * idx + 1
            right = 2 * idx + 2
            smallest = idx

            if left < n and self.heap[left] < self.heap[smallest]:
                smallest = left
            if right < n and self.heap[right] < self.heap[smallest]:
                smallest = right

            if smallest != idx:
                self.heap[idx], self.heap[smallest] = self.heap[smallest], self.heap[idx]
                idx = smallest
            else:
                break

    def enqueue(self, booking_id, priority_score):
        # Create a tuple: (DateTime, tie_breaker, ID)
        element = (priority_score, self.entry_count, booking_id)
        self.entry_count += 1
        
        self.heap.append(element)
        self.heapify_up(len(self.heap) - 1)
    
    def dequeue(self):
        if len(self.heap) == 0:
            return None

        root_value = self.heap[0]
        last_value = self.heap.pop()

        if len(self.heap) > 0:
            self.heap[0] = last_value
            self.heapify_down(0)

        # The booking_id is at index 2 of the tuple
        return root_value[2]
        
    def is_empty(self):
        return len(self.heap) == 0


def allocate_waiting_seat_min_heap(flight_id: int, db):
    """
    Checks the flight's Min-Heap priority queue for waitlisted passengers.
    If waitlisted passengers exist (earliest request time has highest priority),
    pops the highest-priority user, assigns them the newly freed seat,
    and updates their booking status from 'Pending'/'waiting_list' to 'confirmed'.
    """
    from . import model

    waiting_bookings = (
        db.query(model.Booking)
        .filter(
            model.Booking.flight_id == flight_id,
            model.Booking.status.in_(["waiting_list", "pending", "Pending", "WAITLIST"]),
        )
        .all()
    )

    if not waiting_bookings:
        return None

    pq = priority_queue()
    for wb in waiting_bookings:
        pq.enqueue(wb.booking_id, wb.created_at)

    promoted_id = pq.dequeue()
    if promoted_id:
        promoted = db.query(model.Booking).filter(model.Booking.booking_id == promoted_id).first()
        if promoted:
            promoted.status = "confirmed"
            # Assign the newly freed seat to the promoted passenger
            flight = db.query(model.Flight).filter(model.Flight.flight_id == flight_id).first()
            if flight and flight.seats_available > 0:
                flight.seats_available -= 1
            return promoted
    return None


def get_flight_waitlist_length(flight_id: int, db) -> int:
    """
    Return the total number of passengers currently in the Min-Heap waitlist for a flight.
    """
    from . import model

    return (
        db.query(model.Booking)
        .filter(
            model.Booking.flight_id == flight_id,
            model.Booking.status.in_(["waiting_list", "pending", "Pending", "WAITLIST"]),
        )
        .count()
    )


def get_waitlist_ranks_for_flight(flight_id: int, db) -> dict:
    """
    Builds the Min-Heap priority queue from all active waitlist bookings for a flight.
    Pops passengers one-by-one by earliest request time to dynamically determine each booking's 1-based rank.
    If passengers ahead cancel, subsequent passengers dynamically move up in rank (e.g. WL-5 to WL-3).
    Returns: dict mapping booking_id -> current 1-based integer rank {booking_id: rank}
    """
    from . import model

    waiting_bookings = (
        db.query(model.Booking)
        .filter(
            model.Booking.flight_id == flight_id,
            model.Booking.status.in_(["waiting_list", "pending", "Pending", "WAITLIST"]),
        )
        .all()
    )

    if not waiting_bookings:
        return {}

    pq = priority_queue()
    for wb in waiting_bookings:
        pq.enqueue(wb.booking_id, wb.created_at)

    ranks = {}
    current_rank = 1
    while not pq.is_empty():
        bid = pq.dequeue()
        if bid is not None:
            ranks[bid] = current_rank
            current_rank += 1

    return ranks


def get_booking_waitlist_position(flight_id: int, booking_id: int, db) -> int | None:
    """
    Calculates a waitlisted booking's exact current 1-based rank in its flight's Min-Heap queue.
    """
    ranks = get_waitlist_ranks_for_flight(flight_id, db)
    return ranks.get(booking_id)
