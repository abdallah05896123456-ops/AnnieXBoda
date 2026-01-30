#!/bin/bash
set -e

echo "Booting AnnieXMedia AI Environment (G4F Edition)..."

# ===============================
# 1) CPU / BLAS Acceleration
# ===============================
# بنحافظ على إعدادات السرعة عشان معالجة الصوت والبيانات تفضل سريعة
export OMP_NUM_THREADS=16
export MKL_NUM_THREADS=16
export NUMEXPR_NUM_THREADS=16

# ===============================
# 2) Start Bot
# ===============================
echo "Starting AnnieXMedia Bot..."
# تشغيل البوت فوراً بدون أي انتظار
exec nice -n -5 python3 run.py
