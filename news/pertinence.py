"""
EnerX - Filtre de pertinence : ne garder que les articles qui peuvent influencer la valeur d'un token
d'electricite solaire en Tunisie (production, tarifs, STEG, reseau, reglementation, acteurs du solaire).

Principe (plus fin qu'une simple recherche de mots-cles) :
  - termes FORTS  : specifiques a l'energie (steg, solaire, photovoltaique, kWh, tarif de rachat...)
  - termes FAIBLES: trop generiques seuls (energie, gaz, reseau, tarif...) -> ne suffisent jamais
  - expressions EXCLUES retirees avant l'analyse (ex. "Banque centrale" ne doit pas compter comme "centrale")
  Un article est retenu si :
     - son TITRE contient au moins un terme fort, ou
     - son TEXTE contient au moins 5 termes forts DIFFERENTS (un article de bourse ou de finance qui cite
       "electricite" en passant ne passe plus), ou
     - son titre contient un terme faible ET son texte au moins 2 termes forts differents.
  Sont rejetes d'office : les pages qui ne sont pas des articles (archives, recherches populaires, pages de
  contact...) et les articles hors de l'annee courante (voir est_de_cette_annee).
Pour elargir le dictionnaire : ajouter des termes dans FORTS / FAIBLES ci-dessous.
"""
import os
import re
import unicodedata
from datetime import date

# ---- Termes FORTS : (prefixes de mots ; le mot peut continuer : "photovolta" -> photovoltaique) ----
FORTS = [
    # acteurs et institutions
    "steg", "anme", "prosol", "tunur", "elmed", "ministere de l'energie", "agence nationale pour la maitrise de l'energie",
    # solaire / renouvelables
    "solaire", "solar", "photovolta", "panneaux solaires", "centrale solaire", "centrale photovolta", "toits solaires",
    "energie renouvelable", "energies renouvelables", "renouvelable", "transition energetique", "eolien", "hydrogene vert",
    "maitrise energetique", "maitrise de l'energie", "efficacite energetique", "autoproduction", "autoproducteur", "net metering", "mix energetique", "stockage d'energie", "onduleur",
    # electricite / reseau / prix
    "electricite", "reseau electrique", "kwh", "megawatt", "gigawatt", "tarif de rachat", "tarif de l'electricite",
    "prix de l'electricite", "appel d'offres", "delestage", "coupure de courant", "coupures d'electricite", "pic de consommation",
    "interconnexion", "subvention de l'energie", "compensation energetique", "deficit energetique",
    # anglais
    "electricity", "renewable", "power grid", "feed-in", "power purchase agreement",
    # arabe (recherche de sous-chaine)
    "الستاغ", "الشركة التونسية للكهرباء والغاز", "الكهرباء", "كهرباء", "الطاقة الشمسية", "الطاقات المتجددة", "طاقة متجددة",
    "فوتوفولطائي", "الطاقة الكهربائية", "الوكالة الوطنية للتحكم في الطاقة", "محطة شمسية", "الشمسية",
]

# ---- Termes FAIBLES : n'ont de poids que combines a un terme fort ----
FAIBLES = [
    "energie", "energy", "gaz", "centrale", "reseau", "tarif", "panneau", "batterie", "stockage", "coupure", "cybersecurite",
    "faille de securite", "piratage", "cyberattaque", "canicule", "vague de chaleur", "importation", "carburant",
    "طاقة", "الطاقة", "الغاز", "محطة",
]

# ---- Expressions retirees avant analyse (faux amis) ----
# ---- Titres de pages qui ne sont pas des articles (annuaires, archives, menus) : rejetes d'office ----
TITRES_POUBELLE = ["recherches populaires", "archives des", "archives de", "plan du site", "mentions legales",
                   "nous contacter", "contactez-nous", "politique de confidentialite", "a propos", "accueil"]

EXCLUES = [
    "banque centrale", "bct", "centrale d'achat", "centrale syndicale", "centrale des risques", "centrales d'achat",
    "reseau social", "reseaux sociaux", "reseau de distribution commerciale", "energie positive du marche",
    "البنك المركزي",
]


def _normaliser(texte):
    t = unicodedata.normalize("NFD", (texte or "").lower().replace("’", "'"))
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _est_arabe(terme):
    return any("؀" <= c <= "ۿ" for c in terme)


def _compiler(termes):
    out = []
    for t in termes:
        n = _normaliser(t)
        out.append((t, re.compile(re.escape(n) if _est_arabe(n) else r"\b" + re.escape(n))))
    return out


_FORTS = _compiler(FORTS)
_FAIBLES = _compiler(FAIBLES)
_EXCLUES = [_normaliser(x) for x in EXCLUES]


def _nettoyer(texte):
    t = _normaliser(texte)
    for e in _EXCLUES:
        t = re.sub(r"\b" + re.escape(e) + r"\b" if not _est_arabe(e) else re.escape(e), " ", t)
    return t


def _trouves(regexes, texte):
    return {nom for nom, rx in regexes if rx.search(texte)}


def est_de_cette_annee(date_iso, annee=None):
    """Vrai seulement si la date (AAAA-MM-JJ...) est dans l'annee courante. Date absente ou invalide -> faux :
    sans date on ne peut pas savoir si l'article est vieux, donc on ne l'affiche pas.
    L'annee peut etre forcee avec la variable d'environnement ENERX_NEWS_YEAR."""
    annee = int(annee or os.environ.get("ENERX_NEWS_YEAR") or date.today().year)
    return bool(date_iso) and str(date_iso)[:4] == str(annee)


def _page_poubelle(titre):
    t = _normaliser(titre).strip()
    return any(t.startswith(x) or (" - wmc" in t and t.startswith("archives")) for x in TITRES_POUBELLE)


def analyser(titre, texte=""):
    """Retourne (pertinent: bool, termes_forts_trouves: list) pour affichage / debogage."""
    if _page_poubelle(titre):
        return False, []
    t_titre, t_texte = _nettoyer(titre), _nettoyer(texte)
    forts_titre = _trouves(_FORTS, t_titre)
    forts_texte = _trouves(_FORTS, t_texte) | forts_titre
    faibles_titre = _trouves(_FAIBLES, t_titre)
    ok = bool(forts_titre) or len(forts_texte) >= 5 or (bool(faibles_titre) and len(forts_texte) >= 2)
    return ok, sorted(forts_texte)


def est_pertinent(titre, texte=""):
    return analyser(titre, texte)[0]


def a_garder(titre, texte, date_iso):
    """Filtre complet : de l'annee courante ET utile pour la valeur d'un token solaire."""
    return est_de_cette_annee(date_iso) and est_pertinent(titre, texte)
