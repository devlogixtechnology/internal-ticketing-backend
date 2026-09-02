import psutil
import datetime
from django.core.management.base import BaseCommand
from apps.tickets.models import ServerHealthLog

class Command(BaseCommand):
    help = 'Fetches complete server metrics and saves to database'

    def handle(self, *args, **options):
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        
        # Calculate System Uptime
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime_duration = datetime.datetime.now() - boot_time
        days = uptime_duration.days
        hours, remainder = divmod(uptime_duration.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m"

        # Active Network Connections Count
        connections = len(psutil.net_connections())

        log = ServerHealthLog.objects.create(
            cpu_usage=cpu,
            memory_usage=memory,
            disk_usage=disk,
            system_uptime=uptime_str,
            active_connections=connections
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"[{log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Saved! CPU: {cpu}% | RAM: {memory}% | Disk: {disk}%"
            )
        )