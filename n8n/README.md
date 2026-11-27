# Configuração do Innova AI no n8n

Configure os nós abaixo no workflow existente ou importe `innova-ai-sync.json` em **Workflows → Import from File**. Use dois segredos distintos de pelo menos 32 caracteres, guardados nas variáveis da aplicação e nas credenciais **Header Auth** do n8n.

| Nó | Configuração |
| --- | --- |
| **Webhook** | Método `POST`, caminho `innova-produtos`, autenticação por `X-Innova-Token` com o valor de `N8N_WEBHOOK_SECRET`. Em **Respond**, escolha **Using 'Respond to Webhook' node**. |
| **HTTP Request** | Método `POST`, URL `https://SUA-LOJA/api/rag/sync`, autenticação por `X-Sync-Token` com o valor de `INNOVA_SYNC_SECRET`. Envie JSON com `produto_id` definido de `$json.body.produto_id`. |
| **Respond to Webhook** | Ligue à saída do **HTTP Request** e escolha **First Incoming Item** para retornar o resultado da sincronização. |

No **HTTP Request**, use a expressão `{{ { produto_id: $json.body.produto_id } }}` para o corpo JSON e habilite **Retry On Fail** com três tentativas e cinco segundos entre elas. O arquivo exportado também inclui gatilhos de reconciliação. Após publicar o workflow, guarde a **Production URL** em `N8N_WEBHOOK_URL` e recarregue a configuração do Flask.

O webhook recebe um `POST` JSON como `{"produto_id":"6747764df4467f04a1123456"}` depois da gravação no MongoDB. O servidor lê o estado atual do produto a cada chamada, o que permite reenviar eventos e receber entregas fora de ordem. O painel mantém a gravação no MongoDB quando o n8n falha. O envio aguarda até 1,5 segundo pela conexão e até 10 segundos pela resposta do n8n.

No arquivo exportado, a reconciliação agendada envia `{"modo":"reconciliar"}` ao mesmo endpoint. Ela processa até 20 produtos ativos e verifica até 100 vetores por minuto. O cursor de cada etapa fica no Redis e só avança após a etapa ser concluída. Alterações diretas no MongoDB e eventos perdidos são recuperados por esse agendamento. Em um workflow apenas com os três nós da tabela, reenvie eventos com falha ou execute `indexar_produtos.py` para reconciliar o catálogo.

Para forçar nova tentativa de um produto, reenvie o mesmo evento à URL de produção com o cabeçalho configurado. Para avançar a varredura, execute o gatilho manual novamente. O workflow deixa desabilitado o armazenamento de dados de execução, pois o payload original do Webhook pode incluir seu cabeçalho de autenticação. Em caso de falha recorrente, confira a execução manual no editor e as mensagens de sincronização nos logs do Flask. O n8n precisa alcançar a URL do Flask, inclusive quando houver proteção de deployment na Vercel.

## Teste de integração em homologação

Use um Flask acessível ao n8n por HTTPS, apontado para MongoDB, Supabase com a migração pgvector aplicada, Redis e Gemini de homologação. A **Production URL** do workflow de teste deve encaminhar ao mesmo Flask. Guarde `INNOVA_E2E_BASE_URL`, `INNOVA_E2E_ADMIN_EMAIL` e `INNOVA_E2E_ADMIN_PASSWORD` no `.env` local ou no ambiente. Use os mesmos segredos de sincronização e a mesma configuração de MongoDB e Supabase que o Flask de teste usa.

No PowerShell, a partir da raiz do projeto, com as dependências de `requirements-dev.txt` instaladas:

```powershell
$env:INNOVA_SYNC_E2E = '1'
.\.venv\Scripts\python.exe -m pytest -q tests/test_sync_e2e.py
Remove-Item Env:INNOVA_SYNC_E2E
```

O teste cria um produto temporário pelo painel, consulta o MongoDB e verifica o vetor de 384 dimensões pela RPC `buscar_produtos`. Depois repete o evento via n8n para conferir que o vetor segue único, altera o produto, desativa, reativa e exclui. A limpeza tenta remover o produto temporário e seu vetor se alguma etapa falhar. A suíte normal pula esse teste.

[Webhook no n8n](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/) · [Respond to Webhook](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.respondtowebhook/)
