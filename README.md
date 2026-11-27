
# 🏠 Innova EletroMóveis

### Tudo para inovar a sua casa!

## 📌 Sobre o Projeto

A **Innova EletroMóveis** é um sistema de e-commerce de móveis e eletrodomésticos desenvolvido como trabalho da disciplina de **Projeto de Banco de Dados**.

O projeto utiliza o conceito de **Banco de Dados Poliglota**, integrando diferentes tecnologias para gerenciar os dados da aplicação.

## 🚀 Funcionalidades

- Catálogo de móveis e eletrodomésticos.
- Pesquisa e filtragem por categorias.
- Carrossel automático de produtos.
- Carrinho de compras com cálculo do valor total.
- Finalização de pedidos pelo WhatsApp.
- Login administrativo seguro.
- Cadastro, edição e exclusão de produtos.
- Histórico de produtos visualizados recentemente.
- Innova AI para busca semântica e recomendações do catálogo com preço e estoque consultados no MongoDB.

## 🛠️ Tecnologias Utilizadas

| Tecnologia | Finalidade |
|------------|------------|
| Python + Flask | Desenvolvimento do backend |
| HTML, CSS e JavaScript | Interface do site |
| MongoDB | Armazenamento dos produtos |
| Supabase (PostgreSQL) | Autenticação administrativa e índice pgvector do Innova AI |
| Redis | Histórico de visualizações, limite de consultas e progresso da sincronização |
| Gemini API | Embeddings e seleção contextual de produtos |
| n8n | Sincronização automatizada do índice vetorial |
| WhatsApp | Finalização dos pedidos |

## 🗄️ Banco de Dados Poliglota

O sistema utiliza três bancos de dados:

- **MongoDB:** armazena os produtos, preços, imagens e estoque.
- **Supabase:** gerencia as permissões administrativas e armazena o índice vetorial do catálogo.
- **Redis:** armazena dados temporários do site, limita as consultas ao assistente e registra o progresso da sincronização.

## Innova AI

1. No **SQL Editor** do Supabase, execute [`sql/supabase_innova_ai.sql`](sql/supabase_innova_ai.sql). O script usa a tabela existente, valida `vector(384)`, instala a função `buscar_produtos`, cria o índice HNSW de cosseno e restringe o acesso à função e aos vetores ao backend. A coluna `modelo_embedding` identifica vetores compatíveis com as buscas do site.
2. Preencha `GEMINI_API_KEY` no `.env` local junto com as configurações de MongoDB, Redis e Supabase. Use a mesma origem de dados que a loja que pretende indexar.
3. Com o ambiente virtual instalado no Windows, execute `.\.venv\Scripts\python.exe indexar_produtos.py` no PowerShell, na raiz do projeto. O comando atualiza o conteúdo alterado e remove vetores de produtos desativados ou excluídos. Se interrompido, pode ser executado novamente.
4. Configure a automação conforme o [guia do n8n](n8n/README.md) e preencha no servidor as variáveis do `.env.example`. Na Vercel, configure `FLASK_COOKIE_SECURE=1` e as credenciais de Gemini, MongoDB, Redis e Supabase no ambiente **Production** do projeto. Em desenvolvimento local por HTTP, mantenha `FLASK_COOKIE_SECURE=0`. [Variáveis de ambiente da Vercel](https://vercel.com/docs/environment-variables)
5. Abra **Fale com a IA** e consulte uma categoria com orçamento, por exemplo **Sofás até R$ 2.000**. Abra um card e confira o preço na página do produto.

O botão aparece nas páginas públicas da loja. As consultas ao RAG são habilitadas por padrão. Se `INNOVA_AI_ENABLED=0`, o botão abre a conversa e o envio informa que o assistente está temporariamente indisponível. Para reativar as consultas, use `INNOVA_AI_ENABLED=1` ou remova a variável. Na Vercel, mudanças nas variáveis valem para os próximos deploys. [Variáveis de ambiente da Vercel](https://vercel.com/docs/environment-variables)

A indexação e a busca usam `gemini-embedding-2` com 384 dimensões via HTTPS. A Vercel limita o runtime às versões de Python disponíveis na plataforma e usa Python 3.12 por padrão. Os scripts e a aplicação também funcionam localmente em Python 3.10. [Gemini Embeddings](https://ai.google.dev/gemini-api/docs/embeddings) · [Runtime Python da Vercel](https://vercel.com/docs/functions/runtimes/python)

O assistente limita chamadas a oito consultas por IP e 60 no total por minuto. As conversas ficam na aba do navegador. Cada consulta envia a pergunta e até duas perguntas anteriores ao Gemini, junto com os dados públicos dos candidatos na etapa de seleção. O aplicativo monta as respostas e os cards com os produtos confirmados no MongoDB. Quando o Gemini falha na seleção, o site pode exibir os resultados da busca vetorial já verificados. Quando o Redis, o MongoDB, os embeddings ou a busca vetorial falham, o assistente informa indisponibilidade e as demais rotas seguem com seu tratamento atual.

## 📱 Finalização de Compras

O cliente adiciona produtos ao carrinho e, ao finalizar a compra, é redirecionado ao WhatsApp da loja.

A mensagem é gerada automaticamente, contendo os nomes dos produtos, quantidades e o valor total do pedido.

## 🎬 Vídeo de Demonstração

O vídeo apresenta o funcionamento do e-commerce, incluindo:

- Login do administrador pelo Supabase.
- Cadastro de produtos no MongoDB.
- Histórico de visualizações com Redis.
- Carrinho de compras.
- Finalização do pedido pelo WhatsApp.

### ▶️ Links

[🎥 Assistir à demonstração do sistema] https://drive.google.com/file/d/1gQCmnKTpDYIDv5JZNjpS6IbpGIkXl753/view?usp=drive_link

## 👨‍💻 Desenvolvedores

- **Thiago Borges**
- **Ismael Sales**

**Disciplina:** Projeto de Banco de Dados  
**Avaliação:** 3ª Avaliação  
**Ano:** 2026

---

### 🧡 Innova EletroMóveis
**Tudo para inovar a sua casa!**
