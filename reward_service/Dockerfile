# Tahap 1: Pilih base image Python yang efisien dan stabil.
FROM python:3.9-slim

# Tahap 2: Set direktori kerja di dalam kontainer.
WORKDIR /app

# Tahap 3: Salin file requirements terlebih dahulu dan install dependensi.
# Ini memanfaatkan cache Docker, mempercepat build jika dependensi tidak berubah.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tahap 4: Salin semua sisa file proyek ke dalam direktori kerja.
# Ini termasuk app.py dan folder templates.
COPY . .

# Tahap 5: Beri tahu Docker bahwa kontainer akan berjalan di port 5005.
# Berdasarkan app.run(port=5005) di kode Anda.
EXPOSE 5005

# Tahap 6: Perintah untuk menjalankan aplikasi saat kontainer dimulai.
# Menggunakan Gunicorn sebagai server produksi.
CMD ["gunicorn", "--bind", "0.0.0.0:5005", "app:app"]