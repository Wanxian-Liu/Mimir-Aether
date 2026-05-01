def _deliver_output(job: Dict[str, Any], content: str):
    """Deliver job output to configured target."""
    deliver = job.get("deliver", "local")
    
    if deliver == "local":
        return
    
    logger.info("Delivering job output to: %s", deliver)
    
    # For now, just log - full delivery requires platform adapters
    # This will be expanded when we integrate with the gateway
    try:
        # Try to use gateway delivery if available
        from gateway.delivery import deliver_message
        deliver_message(deliver, content, job.get("name", "Cron Job"))
    except Exception as e:
        logger.warning("Delivery failed: %s", e)

def start_scheduler(interval: int = 60):
    """Start the scheduler loop. Runs tick() every `interval` seconds."""
    import time
    
    logger.info("Starting scheduler (interval=%ds)", interval)
    
    try:
        while True:
            tick()
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped")
    finally:
        _release_lock()

# Run tick once if executed directly
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    tick()
