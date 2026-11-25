# ROB RUN Türkçe

**ROB RUN** için açık kaynak, ücretsiz **Türkçe yama**: oyunun tamamını Türkçeye çevirir, oyunun fontlarına Türkçe harfleri ekler ve yanında bir **suç rehberi** sunar.

> Resmî değildir. Kefir veya ROB RUN geliştiricileriyle bir bağı yoktur. Oyunun metinleri, fontları ve diğer içerikleri sahiplerine aittir; bu depo oyun dosyası **içermez**, yamayı her oyuncunun kendi oyunundan bilgisayarında üretir.

## Özellikler

- **Tam Türkçe**: menüler, ayarlar, eşyalar, NPC diyalogları, ipuçları, Kodeks (4.879 metin, oyunun 0.7 güncellemesi dahil).
- **Türkçe harfler**: oyunun 5 fontuna `İ ı Ş ş Ğ ğ` (gerekenlere `Ç Ö Ü â î û`) eklenir. Harfler fontun kendi glifleriyle birleştirildiği için stil birebir aynıdır. Türkçe Windows'ta İngilizce oyunda bile görülen "GRAPH CS" (kayıp İ) sorunu da düzelir.
- **Oyun içi rehber**: mekân, anahtar ve değerli eşya açıklamalarına değer/risk/gereken alet satırı (`REHBER`).
- **Program** (`RobRun_Turkce.exe`):
  - **Başlangıç Rehberi**: adım adım, yeni başlayanlar için.
  - **Durumum**: paranı oyun ekranından otomatik okur (Windows OCR) ve sırayla ne alman gerektiğini önerir.
  - **Soygun Hedefleri**, **Anahtar ve Aletler**, **Yükseltmeler**.
- **Oyun güncellenince** tekrar "Kur" demek yeterli; yama yeni sürüme kendini uyarlar.

## Kurulum

### Kolay yol (oyuncular için)
[Releases](../../releases) sayfasından `RobRun_Turkce_Setup.exe` dosyasını indir, çalıştır, ardından programda **Kur ve Oyunu Başlat**'a bas.

> Dosya imzalı olmadığı için Windows "bilgisayarınızı korudu" diyebilir: **Ek bilgi → Yine de çalıştır**.

### Kaynak koddan
1. Depoyu indir (`Code → Download ZIP` ya da `git clone`).
2. **`setup.bat`** dosyasına çift tıkla. Gerekirse [uv](https://docs.astral.sh/uv/)'yi ve Python 3.12'yi kendisi kurar, kütüphaneleri yükler ve bir menü açar:
   - `1` Programı aç
   - `2` Türkçe yamayı kur ve oyunu başlat
   - `3` Türkçe yamayı kaldır
   - `4` Kurulum dosyası derle (`release\RobRun_Turkce_Setup.exe`)

## Güvenli mi?

- **Oyun klasörüne dokunulmaz.** Yama yalnızca Unity'nin önbellek klasörüne kurulur:
  `%USERPROFILE%\AppData\LocalLow\Kefir\ROB RUN\com.unity.addressables`
- Para okuma **sadece ekran görüntüsüyle** yapılır (OBS/Discord yayını gibi). Oyunun belleğine, koduna ya da ağ trafiğine **erişilmez**.
- Kaldırmak için programda **Yamayı Kaldır** (ya da `setup.bat` → `3`). Oyun orijinal hâline döner.

Yine de üçüncü taraf bir yamadır; kullanım sorumluluğu oyuncudadır.

## Nasıl çalışıyor?

| Parça | Dosya | Ne yapar |
|---|---|---|
| Metinler | `robrun_tr/build.py` | Oyunun İngilizce Unity Localization tablosunu okur, `data/strings_tr.json` ile Türkçe paket üretir. `{0}`, `<color>` gibi kodları bozan çeviriyi atlar. |
| Fontlar | `robrun_tr/fonts.py` | TextMeshPro SDF atlaslarına yeni glifler ekler: İ = I + i'nin noktası, Ş = S + Ç'nin çengeli, Ğ = G + Й'nin kavisi. Mesafe alanı (SDF) yeniden hesaplanır. |
| Kurulum | `robrun_tr/install.py` | Addressables kataloğunu önbelleğe kopyalar ve İngilizce paketin adresini (aynı bayt uzunluğunda) Türkçe pakete yönlendirir. |
| Rehber | `robrun_tr/guide.py`, `data/guide_curated.json` | Oyundaki mekân→ganimet verisi + elle yazılmış hedef/anahtar/aşama bilgisi. |
| Canlı para | `robrun_tr/live.py` | Oyun penceresini yakalar, Windows OCR ile `$` tutarlarını okur. |
| Program | `app/main.py`, `app/ui/index.html` | pywebview masaüstü arayüzü. |
| Kurulum sihirbazı | `installer/setup.py`, `tools/build_release.ps1` | Tek dosyalık `Setup.exe` üretir. |

## Katkı

- **Çeviri düzeltmesi**: `data/strings_tr.json` içinde ilgili `"StaticStrings::anahtar"` satırını düzelt. Terimler için `data/glossary.md`'ye uy. `{0}`, `<color=...>` gibi kodlara dokunma.
- **Rehber**: `data/guide_curated.json` → ardından `uv run python robrun_tr/guide.py`.
- Hata/öneri için Issue aç.

## Lisans

Kod ve Türkçe çeviri metinleri [MIT](LICENSE) lisansıyla. Oyunun kendisi ve içeriği bu lisansa dahil değildir.
