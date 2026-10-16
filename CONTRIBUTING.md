# Kontribusi

Gunakan Python 3.11+ dan instal proyek dengan `python -m pip install -e .`.

Sebelum mengajukan perubahan:

```bash
python -m unittest discover -s tests -v
sleeper-token validate
sleeper-token run
python -m pip wheel --no-deps --wheel-dir dist .
```

Tes dan demo default harus tetap offline, tanpa API key. Jangan menambahkan request berbayar ke CI. Adapter API baru memerlukan stub transport untuk penggunaan token, respons kosong/incomplete, timeout, dan kegagalan HTTP.

Untuk fixture baru, ikuti [format skenario](docs/scenarios.md). Sertakan tujuan pengguna, pasangan clean/injected, marker sintetis unik, dan pemeriksaan fakta yang bisa ditinjau. Perubahan evaluator atau denominator harus disertai pembaruan [metodologi](docs/methodology.md).

**Satu commit hanya boleh mengubah satu file**, mengikuti konvensi proyek. Gunakan pesan commit yang menjelaskan fungsi file tersebut. Hindari memasukkan API key, file konfigurasi lokal, virtual environment, atau hasil run pribadi ke Git.

Laporkan hasil mock sebagai simulasi. Temuan model live harus menyebutkan suite/config hash, model yang dikembalikan, pengulangan, cakupan error, batas evaluator, dan contoh output yang sudah ditinjau.
