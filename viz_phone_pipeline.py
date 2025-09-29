"""
viz_phone_pipeline.py — задержка + буфер телефона (RU/EN)
"""
import random, statistics
import matplotlib.pyplot as plt

def simulate(n_tasks=25, seed=7):
    random.seed(seed)
    s  = [random.randint(20, 60) for _ in range(n_tasks)]
    f  = [random.randint(30, 80) for _ in range(n_tasks)]
    c  = [random.randint(10, 40) for _ in range(n_tasks)]
    lat = [a+b+d for a,b,d in zip(s,f,c)]
    read_interval_ms = 120
    time = 0; buf=0; buf_sizes=[]
    for L in lat:
        time += L
        reads = time // read_interval_ms
        for _ in range(int(reads)):
            if buf>0: buf -= 1
        buf += 1
        buf_sizes.append(buf)
    return lat, buf_sizes, statistics.mean(lat)

def main():
    lat, buf_sizes, avg = simulate()
    # Latency chart
    plt.figure(figsize=(8,4.5))
    plt.plot(range(1,len(lat)+1), lat, marker='o')
    plt.title("Задержка до телефона / Latency to Phone (ms)")
    plt.xlabel("Задача / Task #"); plt.ylabel("Задержка, мс / Latency, ms")
    plt.tight_layout(); plt.show()
    # Buffer chart
    plt.figure(figsize=(8,4.5))
    plt.plot(range(1,len(buf_sizes)+1), buf_sizes, marker='s')
    plt.title("Буфер телефона / Phone Buffer Size")
    plt.xlabel("Задача / Task #"); plt.ylabel("Сообщений в буфере / Messages")
    plt.tight_layout(); plt.show()
    print("Average latency (ms):", round(avg,2))

if __name__ == "__main__":
    main()
