# Deutschgiz yayın robotu – kurulum

Bu depo, Instagram gönderilerini **GitHub Actions** ile takvimdeki saatte kendiliğinden yayınlar.
Bilgisayarın açık olması, Meta Business Suite, Windsor ya da Claude gerekmez.

- `schedule.json` → yayın takvimi (gönderi, caption, tarih/saat). Her hafta Claude günceller.
- `2026-47/` … → o haftanın videoları, kapakları ve slaytları (Instagram bu adreslerden indirir).
- `state/published.json` → neyin ne zaman yayınlandığının kaydı (robot yazar).
- `.github/workflows/publish.yml` → robot her 15 dakikada bir çalışır.

## Bir kerelik kurulum (≈20–30 dk)

### 1. Meta uygulaması ve erişim anahtarı
1. https://developers.facebook.com/apps adresine Instagram'ın bağlı olduğu Facebook hesabınla gir → **Create app / Uygulama oluştur**.
2. Kullanım senaryosu olarak **Instagram API** / *"Manage messaging & content on Instagram"* seçeneğini seç. Uygulamaya bir ad ver (ör. `deutschgiz-robot`).
3. Uygulama panelinde **Instagram → API setup with Instagram login** (Instagram girişiyle API kurulumu) bölümüne git.
4. **Generate access tokens / Erişim anahtarı oluştur** kısmında **Add account** ile **deutschgiz** hesabıyla giriş yap ve izinleri onayla.
   Gerekli izinler: `instagram_business_basic` ve `instagram_business_content_publish`.
5. Hesabın yanında çıkan **Generate token** düğmesine bas, anahtarı kopyala. **Bu anahtarı kimseyle, Claude'la da paylaşma.**

> Hesap listede görünmezse: **App roles → Roles → Instagram Testers** bölümünden `deutschgiz`'i ekle, ardından Instagram uygulamasında
> *Ayarlar → Uygulamalar ve web siteleri → Test kullanıcısı davetleri* kısmından daveti kabul et ve 4. adımı tekrarla.
> Uygulamayı "Live" moda almana gerek yok; kendi hesabın için geliştirme modu yeterli.

### 2. Anahtarı GitHub'a gizli değer (secret) olarak ekle
1. https://github.com/brcgldn/deutschgiz-media/settings/secrets/actions
2. **New repository secret** → Name: `IG_ACCESS_TOKEN` → Secret: kopyaladığın anahtar → **Add secret**.

### 3. Deneme çalıştırması
1. https://github.com/brcgldn/deutschgiz-media/actions → soldan **Instagram yayını** → **Run workflow**.
2. `dry_run` işaretli kalsın → **Run workflow**.
3. Çalışma bitince kaydında **"🔑 Anahtar çalışıyor: @deutschgiz"** ve sıradaki gönderiler görünmeli. Hiçbir şey yayınlanmaz.

Bu kadar. Bundan sonra robot her 15 dakikada bir takvime bakar ve saati gelen gönderiyi yayınlar.

## Günlük kullanım

| İstediğin | Yapılacak |
|---|---|
| Bir gönderiyi hemen yayınlamak | Actions → Run workflow → `dry_run` kapalı, `only_id` = `P2` gibi, `force` açık |
| Tüm yayınları durdurmak | `schedule.json` içinde `"paused": true` (Claude'a "yayınları durdur" demen yeterli) |
| Bir şey ters gitti mi? | Başarısız çalışmalarda GitHub sana e-posta atar; ayrıntı Actions kaydında |

**Güvenlik kuralları (robotun içinde):**
- Aynı gönderi iki kez yayınlanmaz (`state/published.json`).
- Saatinden **6 saatten fazla** geç kalan gönderi otomatik yayınlanmaz; atlanır ve çalışma hata verir (e-posta gelir). İstersen `force` ile elle yayınlarsın.
- Yayın adımında bağlantı koparsa sonuç belirsiz sayılır ve **otomatik tekrar denenmez** (çift gönderi olmasın diye); kayıtta ne yapılacağı yazar.

## Bilmen gerekenler
- **Anahtar 60 günde bir yenilenmeli.** Aynı ekrandan yeni anahtar üretip `IG_ACCESS_TOKEN` secret'ını güncelle. Süresi dolunca robot hata verir ve e-posta gelir.
- GitHub'ın zamanlayıcısı yoğun saatlerde birkaç dakika (nadiren daha fazla) gecikebilir; gönderi 12:30 yerine 12:40'ta çıkabilir.
- Depo herkese açık: içindeki dosyalar zaten Instagram'da yayınlanacak içerikler. Anahtar ise secret olarak saklanır ve görünmez.
