# -*- coding: utf-8 -*-
# docker cp setup_pricelists.py gica_odoo:/tmp/setup_pricelists.py
# docker exec -it gica_odoo odoo shell -d gica --db_host=gica_postgres --db_user=odoo --db_password=odoo
# >>> exec(open('/tmp/setup_pricelists.py').read())

# ============================================================
# PRIX UNITAIRES PUBLICS (DA/Tonne) par product_id (variante)
# ============================================================
PRIX_PUBLIC = {
    274: 9300.00,    # CEM I 42.5 N-LH/SR5 - Sac 50kg
    275: 8600.00,    # CEM I 42.5 N-LH/SR5 - Vrac
    276: 9460.00,    # CEM I 42.5 N-LH/SR5 - Sac 50kg Fardelise 2.2T
    277: 7100.00,    # CEM I 52.5 N-SR5 - Sac 50kg
    278: 6300.00,    # CEM I 52.5 N-SR5 - Vrac
    279: 6486.60,    # CEM I 52.5 N-SR5 - Big-Bag charge client
    280: 7250.00,    # CEM I 52.5 N-SR5 - Sac 50kg Fardelise 2.2T
    281: 5750.00,    # CEM II/A-L 32.5 N - Sac 25kg
    282: 6000.00,    # CEM II/A-L 32.5 N - Sac 25kg Fardelise 1.45T
    283: 6000.00,    # CEM II/A-L 32.5 N - Sac 50kg Fardelise
    284: 6600.00,    # CEM II/A-L 42.5 N - Sac 25kg
    285: 6328.20,    # CEM II/A-L 42.5 N - Sac 50kg
    286: 5648.72,    # CEM II/A-L 42.5 N - Vrac
    287: 5835.32,    # CEM II/A-L 42.5 N - Big-Bag charge client
    288: 6790.00,    # CEM II/A-L 42.5 N - Sac 25kg Fardelise 1.45T
    289: 6495.00,    # CEM II/A-L 42.5 N - Sac 50kg Fardelise 2.2T
    262: 6600.00,    # CEM II/A-L 42.5 R - Sac 25kg
    263: 6328.20,    # CEM II/A-L 42.5 R - Sac 50kg
    264: 5648.72,    # CEM II/A-L 42.5 R - Vrac
    265: 5835.32,    # CEM II/A-L 42.5 R - Big-Bag charge client
    266: 6790.00,    # CEM II/A-L 42.5 R - Sac 25kg Fardelise 1.45T
    267: 6495.00,    # CEM II/A-L 42.5 R - Sac 50kg Fardelise 2.2T
    290: 8600.00,    # Well Cement - Vrac
    291: 9500.00,    # Well Cement - Big-Bag sortie usine
    268: 4200.00,    # Clinker - Vrac
}

# ============================================================
# REMISES % sur Tarif Public (None = pas de regle)
# Pour changer un % : modifier ici et reexecuter le script
# ============================================================
REMISES_SODISMAC = {
    274: 7,  275: 10, 276: 7,
    277: 7,  278: 10, 279: None, 280: 7,
    281: 7,  282: 7,  283: None,
    284: 7,  285: 7,  286: 10, 287: None, 288: 7, 289: 7,
    262: 7,  263: 7,  264: 10, 265: None, 266: 7, 267: 7,
    290: None, 291: None, 268: None,
}

REMISES_AUTRE_CLIENT = {
    274: 4,  275: 5,  276: 2,
    277: 4,  278: 5,  279: None, 280: 2,
    281: 4,  282: 2,  283: None,
    284: 4,  285: 4,  286: 5,  287: None, 288: 2, 289: 2,
    262: 4,  263: 4,  264: 5,  265: None, 266: 2, 267: 2,
    290: None, 291: None, 268: None,
}

REMISES_EXPORTATION = {
    274: 10, 275: 10, 276: 10,
    277: 10, 278: 10, 279: 10, 280: 10,
    281: 10, 282: 10, 283: 10,
    284: 10, 285: 10, 286: 10, 287: 10, 288: 10, 289: 10,
    262: 10, 263: 10, 264: 10, 265: 10, 266: 10, 267: 10,
    290: 10, 291: 10, 268: None,
}

# ============================================================
# EXECUTION
# ============================================================
PricelistItem = env['product.pricelist.item']
Pricelist     = env['product.pricelist']

pl_public   = Pricelist.search([('name', '=', 'GICA - Tarif Public (Usine) (DZD)')], limit=1)
pl_sodismac = Pricelist.search([('name', '=', 'GICA - Tarif SODISMAC (DZD)')],       limit=1)
pl_autre    = Pricelist.search([('name', '=', 'GICA - Tarif Autre Client (DZD)')],   limit=1)
pl_export   = Pricelist.search([('name', '=', 'GICA - Tarif Exportation (DZD)')],    limit=1)

if not pl_public:
    print("ERREUR : Tarif Public INTROUVABLE - arret")
    raise SystemExit

# --- Tarif Public : prix fixe par variante ---
pl_public.item_ids.unlink()
for product_id, prix in PRIX_PUBLIC.items():
    PricelistItem.create({
        'pricelist_id':  pl_public.id,
        'applied_on':    '0_product_variant',
        'product_id':    product_id,
        'compute_price': 'fixed',
        'fixed_price':   prix,
    })
print("Tarif Public : {} regles creees".format(len(PRIX_PUBLIC)))

# --- Pricelists avec remise : formule basee sur Tarif Public ---
# compute_price='formula', base='pricelist', base_pricelist_id=pl_public
# price_discount = remise en %
# Ainsi le commercial peut changer le % directement dans Odoo
# et le prix se recalcule automatiquement depuis Tarif Public

def creer_remises_formule(pricelist, remises, nom):
    if not pricelist:
        print("{} : INTROUVABLE".format(nom))
        return
    pricelist.item_ids.unlink()
    count = 0
    for product_id, remise in remises.items():
        if remise is None:
            continue
        PricelistItem.create({
            'pricelist_id':      pricelist.id,
            'applied_on':        '0_product_variant',
            'product_id':        product_id,
            'compute_price':     'formula',
            'base':              'pricelist',
            'base_pricelist_id': pl_public.id,
            'price_discount':    remise,
        })
        count += 1
    print("{} : {} regles creees (formule sur Tarif Public)".format(nom, count))

creer_remises_formule(pl_sodismac, REMISES_SODISMAC,     'SODISMAC')
creer_remises_formule(pl_autre,    REMISES_AUTRE_CLIENT, 'Autre Client')
creer_remises_formule(pl_export,   REMISES_EXPORTATION,  'Exportation')

env.cr.commit()
print("DONE")