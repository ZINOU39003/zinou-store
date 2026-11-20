<p align="center"><img src="store/icons/zinou-store.svg" width="140"></p>
<h1 align="center">Zinou Store</h1>
<p align="center">متجر تطبيقات أندرويد خاص — عربي • Français • English</p>

<p align="center"><a href="https://github.com/ZINOU39003/zinou-store/releases/latest/download/ZinouStore.apk"><b>⬇️ تحميل المتجر / Télécharger / Download</b></a></p>

---

## كيف يعمل
- **store/apps.json**: قائمة التطبيقات وإصداراتها (قاعدة بيانات المتجر).
- **Releases**: استضافة ملفات APK مجاناً (حتى 2 جيجابايت للملف، بلا حد للعدد أو التنزيلات).
- **Actions**: يبني ملف ZinouStore.apk تلقائياً عند تعديل الكود.

## إضافة تطبيق
1. **Releases → Draft a new release**، اكتب وسماً مثل `myapp-v1.0`، أرفق ملف APK، ثم Publish.
2. أضف التطبيق في `store/apps.json`:

```json
{
  "packageName": "com.example.myapp",
  "name": "My App",
  "name_ar": "تطبيقي",
  "name_fr": "Mon app",
  "description": "Short description",
  "description_ar": "وصف قصير",
  "description_fr": "Description courte",
  "icon": "https://raw.githubusercontent.com/ZINOU39003/zinou-store/main/store/icons/myapp.png",
  "versionCode": 1,
  "versionName": "1.0",
  "size": "100 MB",
  "apkUrl": "https://github.com/ZINOU39003/zinou-store/releases/download/myapp-v1.0/myapp.apk",
  "changelog": "First release",
  "changelog_ar": "أول إصدار",
  "changelog_fr": "Première version"
}
```

- الحقول `_ar` و`_fr` اختيارية؛ إن لم توجد يظهر الحقل العام.
- `packageName` = `applicationId` لتطبيقك، و`versionCode` يجب أن يطابق الرقم داخل ملف APK.
- الأيقونة: ارفع صورة PNG أو SVG إلى مجلد `store/icons`.

## نشر تحديث
1. زِد `versionCode` في تطبيقك ووقّعه **بنفس المفتاح** السابق.
2. ارفعه في Release جديد.
3. حدّث `versionCode` و`versionName` و`apkUrl` و`changelog` في apps.json.

يظهر زر "تحديث" فوراً في المتجر، ويصل إشعار للمستخدمين خلال ~6 ساعات.

## تحديث المتجر نفسه
كل تعديل على الكود يبني إصداراً جديداً `store-vN`. ضع الرقم N في `versionCode` الخاص بـ `com.zinou.store` داخل apps.json.
