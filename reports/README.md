# Hasil lokal

Jalankan `sleeper-token run` untuk membuat direktori hasil baru di sini. Hasil run diabaikan Git karena berisi full prompt, output, dan konfigurasi eksperimen. Contoh simulasi yang sengaja dipublikasikan tersedia di [docs/demo-report.md](../docs/demo-report.md).

- `calls.jsonl`: log yang di-flush setelah setiap panggilan.
- `results.json`: metadata, konfigurasi, hash, semua record, dan agregasi.
- `report.md`: perbandingan dan hasil per panggilan.

Direktori yang sudah ada tidak ditimpa. Setelah run terputus, log mempertahankan panggilan yang sudah selesai, tetapi belum ada resume otomatis atau laporan agregat untuk run parsial.
