# استخدام Python 3.11 slim للحصول على صورة أصغر
FROM python:3.11-slim

# تعيين المتغيرات
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# إنشاء مجلد العمل
WORKDIR /app

# نسخ ملف المكتبات
COPY deployment_requirements.txt requirements.txt

# تثبيت المكتبات
RUN pip install --no-cache-dir -r requirements.txt

# إنشاء مستخدم غير root للأمان
RUN groupadd -r botuser && useradd -r -g botuser botuser

# إنشاء مجلد البيانات وإعطاء الصلاحيات
RUN mkdir -p /app/data && chown -R botuser:botuser /app/data

# نسخ كود البوت
COPY --chown=botuser:botuser . .

# التبديل إلى المستخدم غير root
USER botuser:botuser

# فتح المنفذ للويب كونسول (اختياري)
EXPOSE 5000

# تشغيل البوت
CMD ["python", "main.py"]
