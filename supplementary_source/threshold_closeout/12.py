
cpath = ARTIFACT / "finalization_run" / "analysis_c2st_resolution_map.csv"
C = pd.read_csv(cpath)
print("Resolution map shape:", C.shape)
print("Columns:", list(C.columns))
display(C.head(20))

# Identify numeric AUC columns and calculate sensitivity per row.
auc_cols=[c for c in C.columns if "auc" in c.lower() and pd.api.types.is_numeric_dtype(C[c])]
print("Numeric AUC columns:",auc_cols)
thresholds=[0.9940,0.9945,0.9950,0.9955,0.9960]
summary=[]
for t in thresholds:
    row={"ceiling":t}
    for c in auc_cols:
        row[c+"_below"]=int((pd.to_numeric(C[c],errors="coerce")<t).sum())
    summary.append(row)
display(pd.DataFrame(summary))
