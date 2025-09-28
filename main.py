from dataclasses import dataclass

@dataclass
class Robot:
    name: str
    task: str

    def work(self) -> str:
        return f"Я {self.name}, моя задача: {self.task}"

def simulate():
    robots = [
        Robot("Робот-датчик", "Собираю данные (температура, свет, газ)"),
        Robot("Робот-аналитик", "Фильтрую и усредняю данные на туманном узле (fog)"),
        Robot("Робот-курьер", "Отправляю результат потребителю"),
    ]
    for r in robots:
        print(r.work())

if __name__ == "__main__":
    print("Старт мини-симуляции распределённой системы роботов 🤖")
    simulate()
