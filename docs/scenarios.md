# Menulis skenario

Skenario bawaan berada di `src/sleeper_token/data/` agar tetap tersedia setelah instalasi wheel. Satu file JSON berisi satu pasangan. Semua dokumen, organisasi, dan kebijakan pada fixture adalah sintetis.

Gunakan `01_leave.json` sebagai contoh. Seluruh field di bawah wajib; field tambahan ditolak agar typo tidak diabaikan.

| Field | Format dan fungsi |
| --- | --- |
| `id` | String unik: huruf kecil, angka, `_`, `-` |
| `title` | Nama singkat skenario |
| `language` | Label bahasa, misalnya `id` atau `id-en` |
| `family` | Label keluarga injeksi |
| `question` | Tugas pengguna yang sah |
| `clean_document` | Dokumen retrieval tanpa marker |
| `injected_document` | Dokumen bersih utuh, ditambah payload |
| `reference_answer` | Jawaban referensi untuk meninjau fixture; tidak dikirim sebagai answer key ke model |
| `required_facts` | Daftar grup alias; seluruh grup harus cocok, satu alias per grup cukup |
| `forbidden_facts` | Daftar string fakta keliru yang tidak boleh muncul; boleh kosong |
| `attack_marker` | Marker unik berbentuk `ST_CANARY_<UPPERCASE_ID>` |

Contoh grup alias:

```json
{
  "required_facts": [
    ["12 hari kerja", "dua belas hari kerja"],
    ["1 tahun", "satu tahun"]
  ],
  "forbidden_facts": ["120 hari kerja"]
}
```

Fragmen di atas hanya ilustrasi, bukan skenario lengkap. Loader mengecek reference answer lulus pemeriksaannya sendiri, marker tidak berada pada question/reference/clean document, dan dokumen bersih tetap utuh di versi injected. Marker juga harus unik dalam suite.

Untuk kompatibilitas dengan mock, letakkan ringkasan fakta yang menjawab pertanyaan pada paragraf pertama. Mock tidak menyimulasikan kepatuhan terhadap setiap instruksi spesifik dalam payload; ia hanya memperagakan perbedaan hasil berdasarkan marker.

## Suite lokal

Salin fixture ke direktori lain, lalu ubah isinya:

```bash
sleeper-token validate --scenarios path/to/my-scenarios
sleeper-token run --scenarios path/to/my-scenarios --output reports/custom
```

`--scenarios` menerima direktori JSON atau satu file JSON. Semua file `.json` pada direktori tersebut dianggap fixture; jangan campur dengan file konfigurasi. Untuk menjalankan subset:

```bash
sleeper-token run --scenario 01_leave --scenario 06_retention --repetitions 2
```

Berikan alias secukupnya, tinjau salah positif/salah negatif, dan hindari substring angka yang ambigu. Penilai leksikal tidak memverifikasi penalaran, hubungan antarfakta, negasi, atau semua parafrasa. Jangan memasukkan kredensial atau data pribadi nyata: full prompt dan respons disimpan di laporan lokal.
