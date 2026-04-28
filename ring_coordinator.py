# ring_coordinator.py - 极简四环协调器
class RingCoordinator:
    def __init__(self):
        self.rings = {}

    def register_ring(self, name, priority=0):
        self.rings[name] = {"priority": priority, "active": False}

    def coordinate(self):
        sorted_rings = sorted(self.rings.items(), key=lambda x: x[1]["priority"])
        return [name for name, _ in sorted_rings]


if __name__ == "__main__":
    rc = RingCoordinator()
    rc.register_ring("thought", 1)
    rc.register_ring("action", 2)
    rc.register_ring("verify", 3)
    print("协调顺序:", rc.coordinate())
