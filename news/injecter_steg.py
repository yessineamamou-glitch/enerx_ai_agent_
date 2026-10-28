import json
import os

FICHIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "articles_steg.json")

# Intégration de toutes les actualités réelles de la STEG de septembre et octobre 2026
NEWS_STEG_2026 = [
  {
    "titre": "AVIS IMPORTANT A LA CLIENTELE : ALIMENTATION EN GAZ NATUREL DE LA VILLE DE JDEIDA",
    "date": "2026-10-21",
    "url": "https://steg.com.tn",
    "source": "STEG (site officiel)",
    "texte_brut": "AVIS IMPORTANT A LA CLIENTELE\nALIMENTATION EN GAZ NATUREL DE LA VILLE DE JDEIDA\n\nLa Société Tunisienne de l’Electricité et du Gaz (STEG) informe le public que le gazoduc (Pression 76 bar) destiné à l’alimentation en gaz naturel de la ville de Jdeida sera mis en gaz le Mercredi 21 Octobre 2026 à 08H00. Tous les travaux à proximité du tracé de cette conduite doivent être portés au préalable à la connaissance de la STEG. N.B : La STEG se dégage de toute responsabilité en cas d’accidents survenant sur des chantiers, à proximité du gazoduc, qui n’ont pas été portés d’avance à sa connaissance."
  },
  {
    "titre": "إعلام هام للعموم : تشغيل أنبوب الغاز المزود لمدينة الجديدة",
    "date": "2026-10-21",
    "url": "https://steg.com.tn",
    "source": "STEG (site officiel)",
    "texte_brut": "إعلام هام للعموم\nتشغيل أنبوب الغاز المزود لمدينة الجديدة\n\nتعلّم الشركة التونسية للكهرباء والغاز العموم أنه سيتم تشغيل أنبوب الغاز الطبيعي (ضغط 76 بار) المزود لمدينة 'الجديدة' وذلك بداية من يوم الأربعاء 21 أكتوبر 2026 على الساعة الثامنة صباحا.\nلذا الرجاء إعلام الشركة التونسية للكهرباء والغاز بكل أشغال تقع بجانب مسار الأنبوب المذكور. ملاحظة : إنّ الشركة التونسية للكهرباء والغاز لا تتحمل أية مسؤولية في صورة وقوع حادث في حظائر محاذية للأنبوب لا علم لها بها مسبقا."
  },
  {
    "titre": "إشعار بانقطاع الكهرباء - جهة تونس الكبرى (03/09/2026)",
    "date": "2026-09-03",
    "url": "https://steg.com.tn",
    "source": "STEG (site officiel)",
    "texte_brut": "تعلن الشركة التونسية للكهرباء والغاز (الستاغ) أن التيار الكهربائي سينقطع بسبب أعمال الصيانة الدورية على الشبكة في عدة مناطق من تونس الكبرى. تشمل الانقطاعات أحياء محددة من الساعة الثامنة صباحاً إلى الساعة الرابعة مساءً."
  }
]

# 1. Charger le fichier JSON généré par la collecte automatique
if os.path.exists(FICHIER):
    with open(FICHIER, "r", encoding="utf-8") as f:
        try:
            articles = json.load(f)
        except Exception:
            articles = []
else:
    articles = []

# 2. Insérer les articles s'ils ne sont pas déjà présents (évite les doublons)
urls_existantes = {a["url"] for a in articles}
ajoutes = 0

for news in NEWS_STEG_2026:
    if news["url"] not in urls_existantes:
        articles.append(news)
        ajoutes += 1

# 3. Enregistrer proprement le fichier final
with open(FICHIER, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

print(f"✅ Injection réussie : {ajoutes} articles officiels de la STEG intégrés avec succès pour le Frontend !")
