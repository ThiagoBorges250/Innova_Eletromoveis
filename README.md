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

O Innova AI é o assistente de compras da loja. Pelo botão **Fale com a IA**, o cliente pode pedir recomendações por categoria ou orçamento, como **Sofás até R$ 2.000**. A resposta aparece no chat com fotos, preços e links para os produtos recomendados.

O assistente busca produtos no Supabase pelo significado da pergunta, confere preço e estoque no MongoDB e usa o Gemini para selecionar as recomendações. O n8n sincroniza o índice de busca quando o catálogo muda.

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

[🎥 Assistir à demonstração do sistema](https://drive.google.com/file/d/1gQCmnKTpDYIDv5JZNjpS6IbpGIkXl753/view?usp=drive_link)

[🎥 Assistir à demonstração do Agente de IA INNOVA AI](https://drive.google.com/file/d/1j3k3_NtdSZlNx8t4u-zMsYTIMSa3IKey/view?usp=sharing)

<< Link para o site >> https://innova-eletromoveis-a95za3c40-basicstore.vercel.app/

## 👨‍💻 Desenvolvedores

- **Thiago Borges**
- **Ismael Sales**

**Disciplina:** Projeto de Banco de Dados  
**Avaliação:** 3ª Avaliação  
**Ano:** 2026

---

### 🧡 Innova EletroMóveis
**Tudo para inovar a sua casa!**
