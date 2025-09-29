"""viz_phone_pipeline.py

Мини-визуализация: 3 шага (датчик → fog → курьер) + мобильный телефон-приёмник.
Показываем:
  • задержку «от датчика до телефона» для каждой задачи;
  • наполняемость буфера телефона во времени;
  • метрика: средняя сквозная задержка (ms).
Стандартные библиотеки: random, statistics, matplotlib.
"""
import random, statistics
import matplotlib.pyplot as plt

def simulate(n_tasks=30, seed=7):
    random.seed(seed)

    # Время обработки (ms) на каждом этапе — простая дискретная модель
    sensor = [random.randint(20, 60) for _ in range(n_tasks)]
    fog    = [random.randint(30, 80) for _ in range(n_tasks)]
    courier= [random.randint(10, 40) for _ in range(n_tasks)]

    # Считаем сквозную задержку на задачу (последовательно: датчик→fog→курьер→телефон)
    latencies = [s + f + c for s, f, c in zip(sensor, fog, courier)]

    # Простейшая модель буфера телефона:
    # телефон «читает» сообщения каждые read_interval_ms миллисекунд
    read_interval_ms = 120
    time = 0
    buffer_sizes = []
    buf = 0
    for i, L in enumerate(latencies, start=1):
        # к моменту доставки i‑го сообщения увеличиваем время
        time += L
        # каждое read_interval_ms телефон читает из буфера одно сообщение (если есть)
        reads = time // read_interval_ms  # сколько раз телефон успел прочитать
        # ограничим списание буфера
        for _ in range(int(reads)):
            if buf > 0:
                buf -= 1
        # новое сообщение приходит в буфер
        buf += 1
        buffer_sizes.append(buf)

    avg_latency = statistics.mean(latencies)
    return latencies, buffer_sizes, avg_latency

def plot(latencies, buffer_sizes):
    # График 1: задержка каждой задачи
    plt.figure(figsize=(8, 4.5))
    plt.plot(range(1, len(latencies)+1), latencies, marker='o')
    plt.title("End-to-End Latency to Phone (ms)")
    plt.xlabel("Task #")
    plt.ylabel("Latency (ms)")
    plt.tight_layout()
    plt.show()

    # График 2: размер буфера телефона по мере поступления задач
    plt.figure(figsize=(8, 4.5))
    plt.plot(range(1, len(buffer_sizes)+1), buffer_sizes, marker='s')
    plt.title("Phone Buffer Size over Tasks")
    plt.xlabel("Task # (arrival order)")
    plt.ylabel("Messages in buffer")
    plt.tight_layout()
    plt.show()

def main():
    latencies, buffer_sizes, avg_latency = simulate()
    print(f"Average end-to-end latency to phone (ms): {avg_latency:.2f}")
    plot(latencies, buffer_sizes)

if __name__ == "__main__":
    main()
