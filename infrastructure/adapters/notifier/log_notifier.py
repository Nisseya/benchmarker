from domain.ports.notifier import NotifierPort

class LogNotifier(NotifierPort):
    async def publish_progress(self, data: dict):
        print(f"PROGRESS UPDATE: Session {data['session_id']} | {data['current']}/{data['total']}")