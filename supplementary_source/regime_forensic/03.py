
# ============================================================
# 2. Extract and hash the exact v1 fixture source + canonical fixture
# ============================================================
V1_NB=json.loads(Path(V1_NOTEBOOK).read_text(encoding="utf-8"))
CANON_NB=json.loads(Path(CANONICAL_NOTEBOOK).read_text(encoding="utf-8"))

def extract_function(nb_obj,name):
    matches=[]
    for ci,c in enumerate(nb_obj["cells"]):
        if c.get("cell_type")!="code": continue
        src="".join(c.get("source",[]))
        try: tree=ast.parse(src)
        except SyntaxError: continue
        lines=src.splitlines()
        for node in tree.body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==name:
                start=min([node.lineno]+[d.lineno for d in getattr(node,"decorator_list",[])])-1
                text="\n".join(lines[start:node.end_lineno])
                matches.append((ci,text))
    if len(matches)!=1:
        raise RuntimeError(f"Expected exactly one definition of {name}, found {len(matches)}")
    return matches[0]

source_audit=[]
for source_name,nb_obj,names in [
    ("KT-v1",V1_NB,["primary_split","ar_noise","make_fixture","task_defs"]),
    ("canonical-v7.14.5",CANON_NB,["build_controlled_iot_fixture"]),
]:
    for name in names:
        ci,text=extract_function(nb_obj,name)
        source_audit.append({
            "source":source_name,"function":name,"cell_index":ci,
            "sha256":stable_hash_text(text),"source_lines":len(text.splitlines())
        })
        globals()[f"SRC_{name}"]=text

SOURCE_AUDIT=pd.DataFrame(source_audit)

EXPECTED_V1_FUNCTION_SHA256 = {
    "primary_split":"e402044fe06f068118e1c8fa572b39572b13d38d873fcabb94df6acc99dd9771",
    "ar_noise":"5b65ee03980f3f520817074fce4b7d44d72c7178701c1ba11d8ea5d127dce428",
    "make_fixture":"d63eab13c7c94e827be86b5baf195ffd75074c95b557eb626c7dcdae7b5b98e7",
    "task_defs":"dafac3d1381d24a48c3cb8c43e1d94135eb961eeba7ef42077b8d7597f0cb159",
}

for name, expected in EXPECTED_V1_FUNCTION_SHA256.items():
    row=SOURCE_AUDIT[(SOURCE_AUDIT["source"]=="KT-v1") & (SOURCE_AUDIT["function"]==name)]
    if len(row)!=1:
        raise AssertionError(f"Missing or duplicated frozen KT-v1 function: {name}")
    actual=str(row.iloc[0]["sha256"])
    if actual!=expected:
        raise AssertionError(
            f"Frozen KT-v1 scientific source mismatch for {name}: expected {expected}, got {actual}. "
            "This means the actual fixture/task construction changed; do not continue."
        )

SOURCE_FUNCTION_HASHES_VERIFIED=True
display(SOURCE_AUDIT)
print("Frozen KT-v1 scientific function hashes verified:",SOURCE_FUNCTION_HASHES_VERIFIED)
SOURCE_AUDIT.to_csv(FORENSIC_ROOT/"manifests"/"source_definition_audit.csv",index=False)

# Show the exact KT10-specific branch from frozen v1 source for review.
src_make=SRC_make_fixture
branch=re.search(
    r'elif context=="regime_unstable":(?P<body>.*?)(?=\n    elif context==|\n    elif context not in)',
    src_make,re.S
)
if not branch:
    raise RuntimeError("Could not extract regime_unstable branch.")
KT10_BRANCH=branch.group(0)
print(KT10_BRANCH)
(FORENSIC_ROOT/"manifests"/"KT10_exact_fixture_branch.txt").write_text(KT10_BRANCH+"\n",encoding="utf-8")
