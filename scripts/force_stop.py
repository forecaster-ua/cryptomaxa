#!/usr/bin/env python3
"""
Скрипт для принудительной остановки планировщика сигналов
"""
import sys
import os
import subprocess
import psutil

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def force_stop_scheduler():
    """Принудительно останавливает планировщик"""
    print("🚨 Начинаем принудительную остановку планировщика...")
    stopped_something = False
    
    try:
        # 1. Останавливаем systemd сервис
        try:
            result = subprocess.run(['sudo', 'systemctl', 'is-active', 'hydra-scheduler'], 
                                  capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip() == 'active':
                print("🛑 Принудительная остановка systemd сервиса...")
                subprocess.run(['sudo', 'systemctl', 'kill', '--signal=SIGKILL', 'hydra-scheduler'], 
                             check=True)
                subprocess.run(['sudo', 'systemctl', 'reset-failed', 'hydra-scheduler'], 
                             check=False)
                print("✅ Systemd сервис принудительно остановлен")
                stopped_something = True
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Не удалось остановить systemd сервис: {e}")
        except FileNotFoundError:
            print("ℹ️  systemctl не найден, пропускаем...")
        
        # 2. Ищем и убиваем процессы планировщика
        processes_killed = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'username']):
            try:
                if (proc.info['cmdline'] and 
                    any('run_scheduler.py' in cmd for cmd in proc.info['cmdline'])):
                    print(f"🔥 Убиваем процесс планировщика PID: {proc.info['pid']} ({proc.info['username']})")
                    proc.kill()
                    processes_killed += 1
                    stopped_something = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        if processes_killed > 0:
            print(f"✅ Убито {processes_killed} процесс(ов) планировщика")
        
        # 3. Ищем и убиваем Python процессы с API клиентами
        api_processes = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if (proc.info['name'] == 'python' and proc.info['cmdline'] and
                    any('hydrabot-fetcher' in cmd for cmd in proc.info['cmdline'])):
                    print(f"🔥 Убиваем связанный процесс PID: {proc.info['pid']}")
                    proc.kill()
                    api_processes += 1
                    stopped_something = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        if api_processes > 0:
            print(f"✅ Убито {api_processes} связанных процесс(ов)")
        
        # 4. Проверяем что все остановлено
        import time
        time.sleep(2)
        
        remaining = 0
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                if (proc.info['cmdline'] and 
                    any('run_scheduler.py' in cmd or 'hydrabot-fetcher' in cmd 
                        for cmd in proc.info['cmdline'])):
                    remaining += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if remaining > 0:
            print(f"⚠️  Обнаружено {remaining} оставшихся процессов")
        else:
            print("✅ Все процессы планировщика остановлены")
        
        if stopped_something:
            print("🎉 Принудительная остановка завершена успешно!")
            return True
        else:
            print("ℹ️  Планировщик не был запущен")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка принудительной остановки: {e}")
        return False

if __name__ == "__main__":
    force_stop_scheduler()