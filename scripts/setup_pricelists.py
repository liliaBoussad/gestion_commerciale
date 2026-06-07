# -*- coding: utf-8 -*-
# ============================================================
# SCRIPT : Remplir les prix dans les listes de prix GICA
# ============================================================
# UTILISATION :
#   1. Copier dans le container :
#      docker cp "C:\Users\PC\Desktop\odoo18\addons\gestion_commerciale\scripts\setup_pricelists.py" odoo18:/tmp/setup_pricelists.py
#
#   2. Lancer le shell Odoo :
#      docker exec -it odoo18 odoo shell -d odoo18 \
#        --db_host db --db_port 5432 --db_user odoo --db_password odoo
#
#   3. Dans le shell :
#      exec(open('/tmp/setup_pricelists.py').read())
# ============================================================

# ============================================================
# PRIX UNITAIRES PUBLICS (DA/Tonne)
# IDs = IDs réels des variantes dans la base odoo18
# ============================================================
PRIX_PUBLIC = {
    148: 9300.00,    # CEM I 42.5 N-LH/SR5 — Sac 50kg
    149: 9460.00,    # CEM I 42.5 N-LH/SR5 — Sac 50kg Fardelise
    150: 8600.00,    # CEM I 42.5 N-LH/SR5 — Vrac
    152: 7100.00,    # CEM I 52.5 N-SR5 — Sac 50kg
    153: 7250.00,    # CEM I 52.5 N-SR5 — Sac 50kg Fardelise
    154: 6300.00,    # CEM I 52.5 N-SR5 — Vrac
    156: 5750.00,    # CEM II/A-L 32.5 N — Sac 25kg
    157: 6000.00,    # CEM II/A-L 32.5 N — Sac 25kg Fardelise
    158: 6000.00,    # CEM II/A-L 32.5 N — Vrac
    160: 6600.00,    # CEM II/A-L 42.5 N — Sac 25kg
    161: 6495.00,    # CEM II/A-L 42.5 N — Sac 50kg Fardelise
    162: 5648.72,    # CEM II/A-L 42.5 N — Vrac
    170: 6600.00,    # CEM II/A-L 42.5 R — Sac 25kg
    171: 6328.20,    # CEM II/A-L 42.5 R — Sac 50kg
    172: 6790.00,    # CEM II/A-L 42.5 R — Sac 25kg Fardelise
    173: 6495.00,    # CEM II/A-L 42.5 R — Sac 50kg Fardelise
    174: 5648.72,    # CEM II/A-L 42.5 R — Vrac
    175: 5835.32,    # CEM II/A-L 42.5 R — Big Bag Client
    164: 8600.00,    # Well Cement — Vrac
    165: 6486.60,    # Well Cement — Big Bag Client
    166: 9500.00,    # Well Cement — Big Bag Scaek
    167: 4200.00,    # Clinker — Vrac
}

# ============================================================
# REMISES % sur prix public
# None = pas de remise applicable
# ============================================================
REMISES_SODISMAC = {
    148: 7,   149: 7,   150: 10,
    152: 7,   153: 7,   154: 10,  165: None,
    156: 7,   157: 7,   158: None,
    160: 7,   161: 7,   162: 10,  163: None,
    170: 7,   171: 7,   172: 7,   173: 7,   174: 10,  175: None,
    164: None, 166: None, 167: None,
}

REMISES_AUTRE_CLIENT = {
    148: 4,   149: 2,   150: 5,
    152: 4,   153: 2,   154: 5,   165: None,
    156: 4,   157: 2,   158: None,
    160: 4,   161: 2,   162: 5,   163: None,
    170: 4,   171: 4,   172: 2,   173: 2,   174: 5,   175: None,
    164: None, 166: None, 167: None,
}

REMISES_EXPORTATION = {
    148: 10,  149: 10,  150: 10,
    152: 10,  153: 10,  154: 10,  165: 10,
    156: 10,  157: 10,  158: 10,
    160: 10,  161: 10,  162: 10,  
    170: 10,  171: 10,  172: 10,  173: 10,  174: 10,  175: 10,
    164: 10,  166: 10,  167: None,
}

# ============================================================
# EXECUTION
# ============================================================
PricelistItem = env['product.pricelist.item']
Pricelist     = env['product.pricelist']

pl_public   = Pricelist.search([('name', '=', 'GICA - Tarif Public (Usine) (DZD)')],   limit=1)
pl_sodismac = Pricelist.search([('name', '=', 'GICA - Tarif SODISMAC (DZD)')],          limit=1)
pl_autre    = Pricelist.search([('name', '=', 'GICA - Tarif Autre Client (DZD)')],      limit=1)
pl_export   = Pricelist.search([('name', '=', 'GICA - Tarif Exportation (DZD)')],       limit=1)

# Tarif Public : prix fixe par variante
if pl_public:
    pl_public.item_ids.unlink()
    for product_id, prix in PRIX_PUBLIC.items():
        PricelistItem.create({
            'pricelist_id':  pl_public.id,
            'applied_on':    '0_product_variant',
            'product_id':    product_id,
            'compute_price': 'fixed',
            'fixed_price':   prix,
        })
    print(f"Tarif Public : {len(PRIX_PUBLIC)} regles creees")
else:
    print("ERREUR : Tarif Public introuvable")

# Tarifs avec remises
def creer_remises(pricelist, remises, nom):
    if not pricelist:
        print(f"ERREUR : {nom} introuvable")
        return
    pricelist.item_ids.unlink()
    count = 0
    for product_id, remise in remises.items():
        if remise is None:
            continue
        PricelistItem.create({
            'pricelist_id':  pricelist.id,
            'applied_on':    '0_product_variant',
            'product_id':    product_id,
            'compute_price': 'percentage',
            'percent_price': remise,
        })
        count += 1
    print(f"{nom} : {count} regles creees")

creer_remises(pl_sodismac, REMISES_SODISMAC,    'SODISMAC')
creer_remises(pl_autre,    REMISES_AUTRE_CLIENT, 'Autre Client')
creer_remises(pl_export,   REMISES_EXPORTATION,  'Exportation')

env.cr.commit()
print("DONE — Toutes les listes de prix sont configurees")