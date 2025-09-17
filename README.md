# DAP Methane SaaS (corrigido)

Este pacote contém uma versão mínima **funcionando** do seu app com `streamlit-authenticator`.

## Como rodar localmente
```bash
pip install -r requirements.txt
streamlit run app.py
```

Login demo:
- Usuário: demo
- Senha: demo123

## Como publicar no Streamlit Cloud
1. Suba estes arquivos para um repositório GitHub (pode ser privado).
2. Em Streamlit Cloud, aponte para `app.py`.
3. Ele já vai pedir login ao abrir.

### Importante
- O erro do `location` foi corrigido removendo o argumento problemático.
- A versão da lib foi fixada: `streamlit-authenticator==0.3.2`.
- Você pode substituir a senha demo por um hash seguro.