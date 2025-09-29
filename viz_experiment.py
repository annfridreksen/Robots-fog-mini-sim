"""
viz_experiment.py — простой график + метрика (RU/EN)
"""
import random, statistics, os, datetime
import matplotlib.pyplot as plt

def simulate_latencies(n_tasks=25, seed=7):
    random.seed(seed)
    s = [random.randint(20, 60) for _ in range(n_tasks)]
    f = [random.randint(30, 80) for _ in range(n_tasks)]
    c = [random.randint(10, 40) for _ in range(n_tasks)]
    return [a+b+d for a,b,d in zip(s,f,c)]

def main():
    lat = simulate_latencies()
    avg = statistics.mean(lat)
    plt.figure(figsize=(8,4.5))
    plt.plot(range(1,len(lat)+1), lat, marker='o')
    plt.title("Сквозная задержка / End-to-End Latency (ms)")
    plt.xlabel("Задача / Task #")
    plt.ylabel("Задержка, мс / Latency, ms")
    plt.gca().text(0.02,0.95,f"Средняя / Average: {avg:.2f} мс",
                   transform=plt.gca().transAxes, va="top", ha="left",
                   bbox=dict(facecolor="white", alpha=0.8, edgecolor="none"))
    plt.tight_layout()
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("results", exist_ok=True)
    out = os.path.join("results", f"exp_{ts}_results.png")
    plt.savefig(out, dpi=160, bbox_inches="tight")
    plt.close()
    print("Saved:", out)
    print("Average latency (ms):", round(avg,2))

if __name__ == "__main__":
    main()
