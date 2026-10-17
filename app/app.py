import random
import time
import threading
import functools
from flask import Flask, request, jsonify
from prometheus_client import Histogram, Counter, Gauge, make_wsgi_app, generate_latest
from werkzeug import Response
from werkzeug.middleware.dispatcher import DispatcherMiddleware

app = Flask(__name__)
app.wsgi_app = DispatcherMiddleware(
    app.wsgi_app, {"/metrics": make_wsgi_app()}
)

# Метрики для алертов
HTTP_REQUEST_DURATION = Histogram(
    "app_http_response_time_seconds",
    "HTTP response time in seconds",
    ["method", "endpoint", "status"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, float("inf")]
)

HTTP_REQUESTS_TOTAL = Counter(
    "app_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

APP_ERROR_RATE = Gauge(
    "app_error_rate_percent",
    "HTTP error rate percentage",
    ["endpoint"]
)

MEMORY_USAGE = Gauge(
    "app_memory_usage_mb",
    "Application memory usage in MB"
)

CPU_USAGE = Gauge(
    "app_cpu_usage_percent",
    "Application CPU usage percentage"
)

# Симуляция использования ресурсов
def simulate_resource_usage():
    while True:
        # Симулируем использование памяти (100-600 MB)
        memory = random.randint(100, 600)
        MEMORY_USAGE.set(memory)
        
        # Симулируем использование CPU (10-90%)
        cpu = random.randint(10, 90)
        CPU_USAGE.set(cpu)
        
        time.sleep(30)

# Запускаем симуляцию в фоновом потоке
resource_thread = threading.Thread(target=simulate_resource_usage, daemon=True)
resource_thread.start()

def observe_http(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        response = func(*args, **kwargs)
        end = time.time()
        
        duration = end - start
        endpoint = request.path
        
        HTTP_REQUEST_DURATION.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code
        ).observe(duration)
        
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code
        ).inc()
        
        return response
    return wrapper

@app.route("/")
@app.route("/health")
@observe_http
def check_health():
    return jsonify({"status": "healthy", "timestamp": time.time()})

@app.route("/metrics")
def metrics():
    # Обновляем метрику error rate перед отдачей метрик
    update_error_rate()
    return Response(generate_latest(), mimetype="text/plain")

def update_error_rate():
    """Обновляем метрику error rate на основе последних запросов"""
    try:
        # В реальном приложении здесь была бы логика расчёта error rate
        # Используем случайное значение
        error_rate = random.randint(1, 15)  # 1-15% error rate
        APP_ERROR_RATE.labels(endpoint="/rand_metrics").set(error_rate)
    except:
        pass

@app.route("/rand_metrics")
@observe_http
def random_metric():
    # Добавляем возможность управления поведением через query parameters
    error_prob = float(request.args.get('error_prob', '0.2'))
    delay = float(request.args.get('delay', '0'))
    
    if delay > 0:
        time.sleep(delay / 1000.0)  # delay в миллисекундах
    
    # Генерируем ответ с заданной вероятностью ошибки
    if random.random() < error_prob:
        response_code = random.choice([500, 502, 503, 504])
        return Response(f"Error: {response_code}", status=response_code)
    else:
        response_code = 200
        return Response(f"Success: {response_code}", status=response_code)

@app.route("/generate_alerts")
@observe_http
def generate_alerts():
    """Эндпоинт для генерации тестовых алертов"""
    alert_type = request.args.get('type', 'all')
    
    if alert_type == 'error_rate':
        # Генерируем высокий error rate
        APP_ERROR_RATE.labels(endpoint="/rand_metrics").set(8.5)
        return jsonify({"status": "high_error_rate_generated", "value": 8.5})
    
    elif alert_type == 'slow_response':
        # Имитируем медленные ответы через задержку
        time.sleep(3.5)
        return jsonify({"status": "slow_response_generated", "delay": 3.5})
    
    elif alert_type == 'high_memory':
        # Устанавливаем высокое использование памяти
        MEMORY_USAGE.set(650)
        return jsonify({"status": "high_memory_generated", "value": 650})
    
    elif alert_type == 'high_cpu':
        # Устанавливаем высокое использование CPU
        CPU_USAGE.set(95)
        return jsonify({"status": "high_cpu_generated", "value": 95})
    
    else:
        # Генерируем все типы алертов
        APP_ERROR_RATE.labels(endpoint="/rand_metrics").set(9.2)
        MEMORY_USAGE.set(620)
        CPU_USAGE.set(88)
        return jsonify({
            "status": "all_alerts_generated",
            "error_rate": 9.2,
            "memory_mb": 620,
            "cpu_percent": 88
        })

@app.route("/reset_metrics")
@observe_http
def reset_metrics():
    """Сброс метрик к нормальным значениям"""
    APP_ERROR_RATE.labels(endpoint="/rand_metrics").set(1.5)
    MEMORY_USAGE.set(250)
    CPU_USAGE.set(35)
    return jsonify({
        "status": "metrics_reset",
        "error_rate": 1.5,
        "memory_mb": 250,
        "cpu_percent": 35
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)