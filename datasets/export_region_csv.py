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

df_dep = pd.read_csv("datasets/effectifs.csv", sep=';', low_memory=False)
df_nat = pd.read_csv("datasets/depenses.csv", sep=';', low_memory=False)

# Détection automatique des régions métropolitaines
regions_metro = sorted(df_dep["region"].dropna().unique().tolist())
regions_metro = [r for r in regions_metro if r not in [1, 2, 3, 4, 6, 99]]


# ─────────────────────────────────────────────
# 3. PREPROCESSING GLOBAL
# ─────────────────────────────────────────────

def is_empty(col):
    return col.isna() | (col.astype(str).str.strip() == "")

# def map_top_to_agg(top):
#     if pd.isna(top):
#         return None
#     top = str(top)
#     if top == "top_SoiCour":
#         return "top_SoiCour"
def map_top_to_agg(top):
    if pd.isna(top):
        return None
    return str(top)


# ─────────────────────────────────────────────
# CLEAN EFFECTIFS (df_dep)
# ─────────────────────────────────────────────

mask_patho_ok = ~(
    df_dep["patho_niv1"].astype(str).str.contains("Total consommants tous régimes", case=False, na=False) |
    df_dep["patho_niv2"].astype(str).str.contains("Total consommants tous régimes", case=False, na=False) |
    df_dep["patho_niv3"].astype(str).str.contains("Total consommants tous régimes", case=False, na=False)
)
df_dep = df_dep[mask_patho_ok].copy()

# GARDER UNIQUEMENT LE NIVEAU TOTAL PATHO_NIV1
df_dep = df_dep[
    df_dep["patho_niv2"].isna() &
    df_dep["patho_niv3"].isna()
].copy()

df_dep["cla_age_5"] = df_dep["cla_age_5"].astype(str)
df_dep = df_dep[df_dep["cla_age_5"].str.match(r"^\d")].copy()

df_dep["libelle_sexe"] = df_dep["libelle_sexe"].astype(str).str.strip().str.lower()
df_dep = df_dep[df_dep["libelle_sexe"].isin(["homme", "hommes", "femme", "femmes"])].copy()
df_dep["libelle_sexe"] = df_dep["libelle_sexe"].replace({"hommes": "homme", "femmes": "femme"})

df_dep["top_agg"] = df_dep["top"].apply(map_top_to_agg)
df_dep = df_dep.rename(columns={"Ntop": "Ntop_dep"})


# ─────────────────────────────────────────────
# CLEAN NATIONAL (df_nat)
# ─────────────────────────────────────────────

df_nat = df_nat[
    is_empty(df_nat["patho_niv2"]) & is_empty(df_nat["patho_niv3"])
].copy()

df_nat = df_nat[
    df_nat["dep_niv_2"].astype(str).str.strip() == "Total des dépenses remboursées"
].copy()

df_nat["top_agg"] = df_nat["top"].apply(map_top_to_agg)

df_nat = (
    df_nat
    .groupby(["annee", "patho_niv1", "top_agg"], as_index=False)
    .agg(Ntop_national=("Ntop", "sum"), montant_national=("montant", "sum"))
)

# # ─────────────────────────────────────────────
# # DIAGNOSTIC : TOPS — comparaison effectifs vs depenses
# # ─────────────────────────────────────────────

# tops_eff = set(df_dep["top_agg"].dropna().unique())
# tops_nat = set(df_nat["top_agg"].dropna().unique())

# only_eff = tops_eff - tops_nat
# only_nat = tops_nat - tops_eff

# tops_par_patho_eff = (
#     df_dep.groupby("patho_niv1")["top_agg"].nunique()
#     .reset_index().rename(columns={"top_agg": "n_tops_effectifs"})
# )
# tops_par_patho_nat = (
#     df_nat.groupby("patho_niv1")["top_agg"].nunique()
#     .reset_index().rename(columns={"top_agg": "n_tops_depenses"})
# )
# tops_compare = tops_par_patho_eff.merge(tops_par_patho_nat, on="patho_niv1", how="outer")
# tops_compare["ratio_tops"] = tops_compare["n_tops_effectifs"] / tops_compare["n_tops_depenses"]
# print("\n" + tops_compare.sort_values("ratio_tops", ascending=False).to_string(index=False))
# print("="*60 + "\n")

# ─────────────────────────────────────────────
# AGRÉGATION EFFECTIFS PAR RÉGION
# ─────────────────────────────────────────────

df_dep_agg = df_dep.groupby(
    ["annee", "region", "patho_niv1", "top_agg", "cla_age_5", "sexe"],
    as_index=False
).agg(
    Ntop_dep=("Ntop_dep", "sum")
)

# ─────────────────────────────────────────────
# CALCUL DU POIDS RÉGIONAL
# weight = Ntop région / Ntop toutes régions (France entière)
# On utilise TOUTES les régions (y compris DOM-TOM) pour que
# la somme des poids == 1 sur la France entière.
# ─────────────────────────────────────────────

ntop_france = (
    df_dep_agg
    .groupby(["annee", "patho_niv1", "top_agg"])["Ntop_dep"]
    .sum()
    .reset_index()
    .rename(columns={"Ntop_dep": "Ntop_dep_france"})
)

df_dep_agg = df_dep_agg.merge(ntop_france, on=["annee", "patho_niv1", "top_agg"], how="left")
df_dep_agg["weight"] = df_dep_agg["Ntop_dep"] / df_dep_agg["Ntop_dep_france"]
df_dep_agg["weight"] = df_dep_agg["weight"].fillna(0)

# ─────────────────────────────────────────────
# MERGE NATIONAL → calcul montant_dep régional
# ─────────────────────────────────────────────

df_dep_agg = df_dep_agg.merge(
    df_nat[["annee", "patho_niv1", "top_agg", "Ntop_national", "montant_national"]],
    on=["annee", "patho_niv1", "top_agg"],
    how="left"
)

# Pathologies sans dépenses nationales → montant_dep = NaN, on force à 0
n_missing_montant = df_dep_agg["montant_national"].isna().sum()
if n_missing_montant > 0:
    print(f"ℹ️  {n_missing_montant} lignes sans montant_national (tops non couverts dans depenses.csv) → montant_dep = 0")
    df_dep_agg["missing_nat"] = df_dep_agg["montant_national"].isna()
    df_dep_agg["montant_national"] = df_dep_agg["montant_national"].fillna(0)

df_dep_agg["montant_dep"] = df_dep_agg["weight"] * df_dep_agg["montant_national"]

# ─────────────────────────────────────────────
# 4. MODE EXECUTION
# ─────────────────────────────────────────────

years = list(range(2015, 2024))

if args.test:
    regions_export = regions_metro[:1]
    years = [2023]
elif not args.all and args.region:
    regions_export = [args.region]
    years = [args.annee]
else:
    regions_export = regions_metro

# ─────────────────────────────────────────────
# 5. PIPELINE EXPORT
# ─────────────────────────────────────────────

df_export = df_dep_agg.copy()

def build_export(region, annee):

    df_region = df_export[df_export["region"] == region].copy()
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
        "00-04": "0-19", "05-09": "0-19", "10-14": "0-19", "15-19": "0-19",
        "20-24": "20-39", "25-30": "20-39", "30-34": "20-39", "35-39": "20-39",
        "40-44": "40-59", "45-49": "40-59", "50-54": "40-59", "55-59": "40-59",
        "60-64": "60-74", "65-69": "60-74", "70-74": "60-74",
        "75-79": "75-89", "80-84": "75-89", "85-89": "75-89",
        "90-94": "90+", "95et+": "90+"
    }

    df_age = df_annee.copy()
    df_age["age_group"] = df_age["cla_age_5"].map(age_mapping)
    df_age = df_age[df_age["age_group"].notna()]

    depenses_age = (
        df_age
        .groupby(["age_group", "patho_niv1"])["montant_dep"]
        .sum()
        .reset_index()
        .rename(columns={"age_group": "age", "patho_niv1": "patho", "montant_dep": "depense"})
    )
    depenses_age.insert(0, "bloc", "depenses_par_age")
    depenses_age.insert(1, "region", region)
    depenses_age.insert(2, "annee", annee)

    age_order = ["0-19", "20-39", "40-59", "60-74", "75-89", "90+"]
    depenses_age["age"] = pd.Categorical(depenses_age["age"], categories=age_order, ordered=True)
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

for region in regions_export:
    print(f"\nRégion {region}")
    for annee in years:
        df_final = build_export(region, annee)
        if df_final is None:
            print(f"  ⏭ skip {region}-{annee}")
            continue
        if args.output:
            file_name = f"{args.output}_{region}_{annee}.csv"
        else:
            file_name = f"data_{region}_{annee}.csv"
        df_final.to_csv(file_name, index=False, sep=';', encoding='utf-8-sig')
        print(f"  ✓ export généré : {file_name}")