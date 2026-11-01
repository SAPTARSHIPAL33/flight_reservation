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

    # EDITED: Accept booking_id and the timestamp (priority_score)
    def enqueue(self, booking_id, priority_score):
        # Create a tuple: (DateTime, tie_breaker, ID)
        element = (priority_score, self.entry_count, booking_id)
        self.entry_count += 1
        
        self.heap.append(element)
        self.heapify_up(len(self.heap) - 1)
    
    # EDITED: Return only the booking_id for the database to use
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
        
    # ADDED: Helper for the FastAPI while loop
    def is_empty(self):
        return len(self.heap) == 0


def allocate_waiting_seat_min_heap(flight_id: int, db):
    """
    Finds the highest-priority waiting-list passenger (earliest created_at timestamp)
    for the specified flight using the Min-Heap priority queue, and promotes them to 'confirmed'.
    If no waiting-list passenger exists, increments seats_available on the flight.
    Returns the promoted booking or None.
    """
    from . import model

    waiting_bookings = (
        db.query(model.Booking)
        .filter(
            model.Booking.flight_id == flight_id,
            model.Booking.status == "waiting_list",
        )
        .all()
    )

    if not waiting_bookings:
        flight = db.query(model.Flight).filter(model.Flight.flight_id == flight_id).first()
        if flight:
            flight.seats_available += 1
        return None

    pq = priority_queue()
    for wb in waiting_bookings:
        pq.enqueue(wb.booking_id, wb.created_at)

    promoted_id = pq.dequeue()
    if promoted_id:
        promoted = db.query(model.Booking).filter(model.Booking.booking_id == promoted_id).first()
        if promoted:
            promoted.status = "confirmed"
            return promoted
    return None
