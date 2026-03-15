#!/bin/bash

# Script để khởi chạy emulator và Flutter app trên Mac M1 với RAM hạn chế
# Tối ưu hóa cho Mac Air M1 8GB

echo "🚀 Khởi chạy emulator và Flutter app..."

# Di chuyển vào thư mục LawApp
cd "$(dirname "$0")" || exit

# Kiểm tra xem emulator đã chạy chưa
if adb devices | grep -q "emulator"; then
    echo "✅ Emulator đã đang chạy"
    DEVICE=$(adb devices | grep emulator | awk '{print $1}')
    echo "📱 Device: $DEVICE"
else
    echo "📱 Đang khởi chạy emulator..."
    # Khởi chạy emulator trong background
    flutter emulators --launch Medium_Phone_API_35 &
    
    # Đợi emulator khởi động
    echo "⏳ Đợi emulator khởi động (30 giây)..."
    sleep 30
    
    # Kiểm tra xem emulator đã sẵn sàng chưa
    echo "🔍 Kiểm tra emulator..."
    adb wait-for-device
    sleep 5  # Đợi thêm để emulator hoàn toàn sẵn sàng
fi

# Kiểm tra lại
if adb devices | grep -q "device"; then
    echo "✅ Emulator đã sẵn sàng!"
    echo "🚀 Đang chạy Flutter app..."
    flutter run
else
    echo "❌ Emulator chưa sẵn sàng. Vui lòng thử lại sau."
    exit 1
fi

