class UnknownBootError(RuntimeError):
    code = "unknown_boot"

    def __init__(self) -> None:
        super().__init__("Telemetry was received for an unregistered device boot.")
