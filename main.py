# ═══════════════════════════════════════════════════════════════
# PATCH v31 — Adicionar antes do bloco "if __name__ == '__main__'"
# ═══════════════════════════════════════════════════════════════

@app.route("/airtable/financeiro/despesas", methods=["GET"])
def get_financeiro_despesas():
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        records_fixas     = airtable_list(BASE_FINANCEIRO, "Despesas Fixas")
        records_variaveis = airtable_list(BASE_FINANCEIRO, "Despesas Variáveis")
        def _mes(f):
            m = f.get("Resumo Mensal(s)", "") or f.get("Resumo Mensal", "")
            if isinstance(m, list):
                return m[0].get("name", "") if m and isinstance(m[0], dict) else (str(m[0]) if m else "")
            return str(m)
        out = []
        for rec in records_fixas:
            f = rec.get("fields", {})
            out.append({
                "id":     rec["id"],
                "nome":   f.get("Fornecedor", f.get("Nome", "")),
                "cat":    f.get("Categoria", ""),
                "valor":  float(f.get("Valor Mensal", 0) or 0),
                "mes":    _mes(f),
                "pago":   bool(f.get("Pago?", False)),
                "fatura": bool(f.get("Fatura Recebida?", False) or f.get("Fatura?", False)),
                "notas":  f.get("Notas", ""),
                "tipo":   "fixa",
            })
        for rec in records_variaveis:
            f = rec.get("fields", {})
            out.append({
                "id":     rec["id"],
                "nome":   f.get("Fornecedor", f.get("Nome", f.get("Descrição", ""))),
                "cat":    f.get("Categoria", f.get("Tipo Despesa", "")),
                "valor":  float(f.get("Valor", 0) or 0),
                "mes":    _mes(f),
                "pago":   bool(f.get("Pago?", False)),
                "fatura": bool(f.get("Fatura Recebida?", False) or f.get("Fatura?", False)),
                "notas":  f.get("Notas", ""),
                "tipo":   "variavel",
            })
        return jsonify({"success": True, "records": out})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/airtable/financeiro/despesas/<record_id>", methods=["PATCH"])
def patch_financeiro_despesa(record_id):
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        body   = request.get_json() or {}
        tipo   = body.get("tipo", "variavel")
        fields = {}
        if "pago"  in body: fields["Pago?"]     = bool(body["pago"])
        if "valor" in body: fields["Valor (€)"]  = float(body["valor"])
        if "notas" in body: fields["Notas"]      = str(body["notas"])
        if not fields:
            return jsonify({"error": "Nenhum campo para actualizar"}), 400
        table  = "Despesas Fixas" if tipo == "fixa" else "Despesas Variáveis"
        result = airtable_patch(BASE_FINANCEIRO, table, record_id, fields)
        cache_clear("despesas")
        return jsonify({"success": True, "record": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/stripe/create-payment-link", methods=["POST"])
def stripe_create_payment_link():
    """Stub — implementar quando Stripe estiver configurado."""
    if not check_key():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({
        "error":   "Stripe não configurado. Adiciona STRIPE_SECRET_KEY no Railway.",
        "success": False,
    }), 501
