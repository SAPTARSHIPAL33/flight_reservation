class FlightNode:
    def __init__(self, flight_id, depart_time, arrival_time, price, seats_available):
        self.flight_id = flight_id
        self.depart_time = depart_time
        self.arrival_time = arrival_time
        self.price = price
        self.seats_available = seats_available
        self.left = None
        self.right = None
        self.height = 1

class FlightAVLTree:
    def insert(self, root, flight_id, depart_time, arrival_time, price, seats_available):
        if not root:
            return FlightNode(flight_id, depart_time, arrival_time, price, seats_available)
        
        # Traverse and insert based on depart_time
        if depart_time < root.depart_time or (depart_time == root.depart_time and flight_id < root.flight_id):
            root.left = self.insert(root.left, flight_id, depart_time, arrival_time, price, seats_available)
        else:
            root.right = self.insert(root.right, flight_id, depart_time, arrival_time, price, seats_available)

        root.height = 1 + max(self.get_height(root.left), self.get_height(root.right))
        balance = self.get_balance(root)

        # Rebalancing for Insertion
        if balance > 1 and (depart_time < root.left.depart_time or (depart_time == root.left.depart_time and flight_id < root.left.flight_id)):
            return self.right_rotate(root)
        if balance < -1 and (depart_time > root.right.depart_time or (depart_time == root.right.depart_time and flight_id > root.right.flight_id)):
            return self.left_rotate(root)
        if balance > 1 and (depart_time > root.left.depart_time or (depart_time == root.left.depart_time and flight_id > root.left.flight_id)):
            root.left = self.left_rotate(root.left)
            return self.right_rotate(root)
        if balance < -1 and (depart_time < root.right.depart_time or (depart_time == root.right.depart_time and flight_id < root.right.flight_id)):
            root.right = self.right_rotate(root.right)
            return self.left_rotate(root)

        return root

    def delete(self, root, depart_time, flight_id):
        if not root:
            return root

        # Navigate using depart_time and flight_id
        if depart_time < root.depart_time or (depart_time == root.depart_time and flight_id < root.flight_id):
            root.left = self.delete(root.left, depart_time, flight_id)
        elif depart_time > root.depart_time or (depart_time == root.depart_time and flight_id > root.flight_id):
            root.right = self.delete(root.right, depart_time, flight_id)
        else:
            if root.left is None:
                temp = root.right
                root = None
                return temp
            elif root.right is None:
                temp = root.left
                root = None
                return temp

            temp = self.get_min_value_node(root.right)
            root.flight_id = temp.flight_id
            root.depart_time = temp.depart_time
            root.arrival_time = temp.arrival_time
            root.price = temp.price
            root.seats_available = temp.seats_available
            root.right = self.delete(root.right, temp.depart_time, temp.flight_id)

        if root is None:
            return root

        root.height = 1 + max(self.get_height(root.left), self.get_height(root.right))
        balance = self.get_balance(root)

        # Rebalancing for Deletion
        if balance > 1 and self.get_balance(root.left) >= 0:
            return self.right_rotate(root)
        if balance > 1 and self.get_balance(root.left) < 0:
            root.left = self.left_rotate(root.left)
            return self.right_rotate(root)
        if balance < -1 and self.get_balance(root.right) <= 0:
            return self.left_rotate(root)
        if balance < -1 and self.get_balance(root.right) > 0:
            root.right = self.right_rotate(root.right)
            return self.left_rotate(root)

        return root

    def search(self, root, depart_time, flight_id):
        if root is None or (root.depart_time == depart_time and root.flight_id == flight_id):
            return root

        if depart_time < root.depart_time or (depart_time == root.depart_time and flight_id < root.flight_id):
            return self.search(root.left, depart_time, flight_id)

        return self.search(root.right, depart_time, flight_id)

    def get_sorted_flights(self, root, result_list=None):
        if result_list is None:
            result_list = []
        
        if root:
            # Traverse Left (Earliest Departure) -> Root -> Right (Latest Departure)
            self.get_sorted_flights(root.left, result_list)
            
            result_list.append({
                "flight_id": root.flight_id,
                "depart_time": root.depart_time,
                "arrival_time": root.arrival_time,
                "price": root.price,
                "seats_available": root.seats_available
            })
            
            self.get_sorted_flights(root.right, result_list)
            
        return result_list

    # The helper functions (get_height, get_balance, left_rotate, right_rotate, get_min_value_node) 
    # remain exactly the same as your previous implementation.