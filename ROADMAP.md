# Roadmap

## v0.1 — fondasi yang dapat dijalankan

- [x] Sepuluh pasangan dokumen retrieval sintetis, Bahasa Indonesia dan campuran Indonesia–Inggris.
- [x] CLI untuk list, validate, dan run, dengan pemilihan skenario dan pengulangan.
- [x] Mock offline berlabel simulasi dan adapter OpenAI Responses API.
- [x] Baseline dan boundary prompt sebagai konfigurasi pembanding.
- [x] Penilaian task success dan marker ASR terpisah, termasuk conditional ASR.
- [x] Log per panggilan, JSON/Markdown report, metadata, token, estimasi biaya, dan hash.
- [x] Tes offline dan konfigurasi CI Windows/Linux.

Implementasi adapter bukan klaim bahwa model live sudah diuji. Tidak ada hasil benchmark live yang disertakan pada rilis awal.

## Berikutnya — kualitas evaluasi

- [ ] Tinjauan manual berlabel dan evaluator semantik yang dikalibrasi terhadap label tersebut.
- [ ] Pengacakan urutan dengan seed yang dicatat dan confidence interval untuk hasil berulang.
- [ ] Suite lebih besar dengan variasi posisi payload dan dokumen benign yang menyerupai instruksi.
- [ ] Batas biaya yang dapat dikonfigurasi, retry eksplisit, dan resume dari log.
- [ ] Perbandingan beberapa model/provider menggunakan schema hasil yang sama.

## Setelah evaluator stabil — pipeline dan agent

- [ ] Integrasi retrieval sungguhan: indeks lokal, dokumen pengalih, dan pelacakan provenance.
- [ ] Tool hasil simulasi dengan pemisahan rencana tindakan dari tindakan yang dieksekusi.
- [ ] Pengujian lintas giliran dan memori sintetis.
- [ ] Perbandingan pertahanan di luar prompt, dengan pengukuran dampak pada tugas sah.
- [ ] Integrasi atau pemetaan suite ke benchmark agent yang sudah ada.

Setiap tahap perlu contoh yang dapat direproduksi dan kriteria keberhasilan yang jelas sebelum memperluas cakupan.
