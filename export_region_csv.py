import os
import argparse
import pandas as pd

# ─────────────────────────────────────────────
# 1. ARGUMENTS
# ─────────────────────────────────────────────

parser = argparse.ArgumentParser(
    description="Export CSV des données intermédiaires traitées (multi-régions / multi-années)"
)

parser.add_argument("--region", type=int, help="Code région (optionnel si --all)")
parser.add_argument("--annee", type=int, default=2023, help="Année de référence")
parser.add_argument("--output", type=str, default=None, help="Nom de sortie (optionnel)")
parser.add_argument("--all", action="store_true", help="Batch toutes les régions + années 2015-2023")
parser.add_argument("--test", action="store_true", help="Mode test (1 région + 1 année)")

args = parser.parse_args()


# ─────────────────────────────────────────────
# 2. LOAD DATA
# ─────────────────────────────────────────────

df_dep = pd.read_csv("datasets/effectifs.csv", sep=';')
df_nat = pd.read_csv("datasets/depenses.csv", sep=';')

# Détection automatique des régions
regions = sorted(df_dep["region"].dropna().unique().tolist())


# ─────────────────────────────────────────────
# 3. PREPROCESSING GLOBAL
# ─────────────────────────────────────────────

df_dep = df_dep.rename(columns={"Ntop": "Ntop_dep"})
df_nat = df_nat.rename(columns={"Ntop": "Ntop_national", "montant": "montant_national"})

for df in [df_dep, df_nat]:
    df["key"] = (
        df["annee"].astype(str) + "|" +
        df["patho_niv1"].astype(str) + "|" +
        df["patho_niv2"].astype(str) + "|" +
        df["patho_niv3"].astype(str) + "|" +
        df["top"].astype(str)
    )

df_nat = df_nat.groupby("key", as_index=False).agg({
    "Ntop_national": "sum",
    "montant_national": "sum"
})

df_dep["weight"] = df_dep["Ntop_dep"] / df_dep.groupby(
    ["annee", "patho_niv1", "patho_niv2", "patho_niv3", "top"]
)["Ntop_dep"].transform("sum")

df_dep["Ntop_national"] = df_dep["key"].map(df_nat.set_index("key")["Ntop_national"])
df_dep["montant_national"] = df_dep["key"].map(df_nat.set_index("key")["montant_national"])
df_dep["montant_dep"] = df_dep["weight"] * df_dep["montant_national"]

df_dep.loc[
    (df_dep["Ntop_national"].isna()) | (df_dep["Ntop_national"] == 0),
    "montant_dep"
] = 0


# ─────────────────────────────────────────────
# 4. MODE EXECUTION
# ─────────────────────────────────────────────

years = list(range(2015, 2024))

if args.test:
    regions = regions[:1]
    years = [2023]

if not args.all and args.region:
    regions = [args.region]
    years = [args.annee]


# ─────────────────────────────────────────────
# 5. PIPELINE EXPORT
# ─────────────────────────────────────────────

def build_export(region, annee):

    df_region = df_dep[df_dep["region"] == region].copy()
    df_annee = df_region[df_region["annee"] == annee].copy()

    if df_region.empty or df_annee.empty:
        return None

    # ─── Bloc 1 : série temporelle ─────────────────
    depenses_par_annee = (
        df_region.groupby("annee")["montant_dep"]
        .sum()
        .sort_index()
        .reset_index()
        .rename(columns={"montant_dep": "depense_totale"})
    )

    depenses_par_annee["depense_totale"] = depenses_par_annee["depense_totale"].round().astype(int)
    depenses_par_annee["yoy_pct"] = depenses_par_annee["depense_totale"].pct_change() * 100
    depenses_par_annee.insert(0, "bloc", "serie_temporelle_yoy")
    depenses_par_annee.insert(1, "region", region)

    # ─── Bloc 2 : top pathologies ─────────────────
    top_pathologies = (
        df_annee.groupby("patho_niv1")["montant_dep"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
        .reset_index()
        .rename(columns={"patho_niv1": "patho", "montant_dep": "depense"})
    )

    top_pathologies.insert(0, "bloc", "top_pathologies")
    top_pathologies.insert(1, "region", region)
    top_pathologies.insert(2, "annee", annee)

    # ─── Bloc 3 : âge ──────────────────────────────

    age_mapping = {
        "00-04": "0-19",
        "05-09": "0-19",
        "10-14": "0-19",
        "15-19": "0-19",

        "20-24": "20-39",
        "25-30": "20-39",
        "30-34": "20-39",
        "35-39": "20-39",

        "40-44": "40-59",
        "45-49": "40-59",
        "50-54": "40-59",
        "55-59": "40-59",

        "60-64": "60-74",
        "65-69": "60-74",
        "70-74": "60-74",

        "75-79": "75-89",
        "80-84": "75-89",
        "85-89": "75-89",

        "90-94": "90+",
        "95et+": "90+"
    }

    df_annee["age_group"] = df_annee["cla_age_5"].map(age_mapping)

    df_annee = df_annee[df_annee["age_group"].notna()].copy()

    depenses_age = (
        df_annee
        .groupby(["age_group", "patho_niv1"])["montant_dep"]
        .sum()
        .reset_index()
        .rename(columns={
            "age_group": "age",
            "patho_niv1": "patho",
            "montant_dep": "depense"
        })
    )

    depenses_age.insert(0, "bloc", "depenses_par_age")
    depenses_age.insert(1, "region", region)
    depenses_age.insert(2, "annee", annee)

    age_order = ["0-19", "20-39", "40-59", "60-74", "75-89", "90+"]

    depenses_age["age"] = pd.Categorical(
        depenses_age["age"],
        categories=age_order,
        ordered=True
    )

    depenses_age = depenses_age.sort_values(["age", "depense"], ascending=[True, False])

    # ─── Bloc 4 : sexe ─────────────────────────────
    sexe_labels = {1: "Homme", 2: "Femme"}

    top5 = top_pathologies["patho"].tolist()

    depenses_sexe = (
        df_annee[df_annee["sexe"].isin([1, 2])]
        .groupby(["patho_niv1", "sexe"])["montant_dep"]
        .sum()
        .reset_index()
        .rename(columns={"patho_niv1": "patho", "montant_dep": "depense"})
    )

    depenses_sexe["sexe"] = depenses_sexe["sexe"].map(sexe_labels)
    depenses_sexe = depenses_sexe[depenses_sexe["patho"].isin(top5)]

    depenses_sexe.insert(0, "bloc", "depenses_par_sexe")
    depenses_sexe.insert(1, "region", region)
    depenses_sexe.insert(2, "annee", annee)

    # ─── concat ─────────────────────────────────────
    df_final = pd.concat(
        [depenses_par_annee, top_pathologies, depenses_age, depenses_sexe],
        ignore_index=True,
        sort=False
    )

    return df_final


# ─────────────────────────────────────────────
# 6. EXECUTION BATCH
# ─────────────────────────────────────────────

for region in regions:
    print(f"\nRégion {region}")

    for annee in years:

        df_final = build_export(region, annee)

        if df_final is None:
            print(f"⏭ skip {region}-{annee}")
            continue

        file_name = args.output if args.output else f"data_{region}_{annee}.csv"

        # si output forcé → éviter écrasement
        if args.output:
            file_name = f"{args.output}_{region}_{annee}.csv"

        df_final.to_csv(
            file_name,
            index=False,
            sep=';',
            encoding='utf-8-sig'
        )

        print(f"✓ export généré : {file_name}")