import pytest

from news import pertinence

GARDES = [
    ("La STEG lance un appel d'offres international pour une centrale solaire", "La Société tunisienne de l'électricité et du gaz..."),
    ("Amel Hamdi, fondatrice de Quatre A Energy : rendre le solaire accessible", "Un parcours dans le photovoltaïque."),
    ("Le site de la STEG inaccessible après une faille de sécurité", "Le site web de la STEG est fermé."),
    ("Hausse du tarif de rachat de l'énergie solaire pour les petits producteurs", ""),
    ("الستاغ تعلن عن مناقصة لمحطة شمسية", ""),
    ("Canicule : record de consommation d'électricité", "Le pic de consommation a été atteint, la STEG évoque des coupures."),
]
RETIRES = [
    ("Wifak Bank lance un appel à candidatures", "Gouvernance du conseil d'administration de la banque, énergie et dynamisme."),
    ("Exportation d'huile d'olive vers le Sénégal", "Les exportateurs tunisiens signent un accord."),
    ("Rentabilité bancaire : les banques tunisiennes face aux taux", "La Banque centrale a relevé son taux directeur. Le secteur de l'énergie reste marginal."),
    ("Un syndicat annonce une grève", "La centrale syndicale appelle ses adhérents."),
    ("Football : le Club africain l'emporte", ""),
]


@pytest.mark.parametrize("titre,texte", GARDES)
def test_garde(titre, texte):
    assert pertinence.est_pertinent(titre, texte), titre


@pytest.mark.parametrize("titre,texte", RETIRES)
def test_retire(titre, texte):
    assert not pertinence.est_pertinent(titre, texte), titre


# ---- fraicheur : seulement les news de l'annee courante ----
from datetime import date


def test_annee_courante():
    an = date.today().year
    assert pertinence.est_de_cette_annee(f"{an}-03-02")
    assert not pertinence.est_de_cette_annee(f"{an - 1}-12-31")
    assert not pertinence.est_de_cette_annee("2017-11-23")


def test_sans_date_refuse():
    assert not pertinence.est_de_cette_annee(None)
    assert not pertinence.est_de_cette_annee("")


def test_a_garder_exige_date_et_sujet():
    an = date.today().year
    titre = "La STEG lance un appel d'offres pour une centrale solaire"
    assert pertinence.a_garder(titre, "", f"{an}-05-01")
    assert not pertinence.a_garder(titre, "", f"{an - 1}-05-01")      # bon sujet, vieille news
    assert not pertinence.a_garder("Football : le Club africain l'emporte", "", f"{an}-05-01")  # bonne date, hors sujet


@pytest.mark.parametrize("titre", ["Recherches populaires", "Archives des Idees et Debats - WMC"])
def test_pages_non_articles(titre):
    assert not pertinence.est_pertinent(titre, "steg electricite solaire photovoltaique kwh")
