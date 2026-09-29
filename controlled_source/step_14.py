
# ============================================================
# 8. Task admission
# ============================================================
def run_admission(context,fixture_seed,frame,times):
    path=checkpoint("task_admission",context,f"fixture{fixture_seed}",suffix=".csv"); meta=path.with_suffix(".json"); cards=candidate_cards(context)
    if load_cp(meta,PROTOCOL_HASH) is not None and path.exists(): table=pd.read_csv(path)
    else:
        bind_fixture(frame,fixture_seed,context,times); records=[]
        for card in cards:
            records.append(assess_task_model(card,SEED0,_key={"card":card.key(),"seed":SEED0,"dataset":RUN_FINGERPRINT["dataset"],"splits":RUN_FINGERPRINT["splits"],"scopes":RUN_FINGERPRINT["scopes"]}))
        table=pd.DataFrame(records); table.to_csv(path,index=False); save_cp(meta,PROTOCOL_HASH,{"context":context,"fixture_seed":fixture_seed,"candidate_cards":len(cards),"admitted_cards":int(table["admissible"].astype(bool).sum())})
    admitted=set(table.loc[table["admissible"].astype(bool),"card_id"].astype(str)); return table,[c for c in cards if c.card_id in admitted]
