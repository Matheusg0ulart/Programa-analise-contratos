# Sistema Multi-Agente Corporativo (Auditoria com IA)

Uma plataforma open-source de auditoria inteligente de contratos, editais e relatórios corporativos. O sistema orquestra múltiplos agentes autônomos (LLMs) que colaboram para extrair, analisar, validar e gerar pareceres sobre documentos extensos.

## Arquitetura e Fluxo

A aplicação utiliza o conceito de **RAG Avançado** (Retrieval-Augmented Generation) integrado a um fluxo de **Agentes de Estado (LangGraph)**.

O pipeline é composto por 4 agentes principais operando em cadeia:
1. **Extrator (Agent 1):** Realiza a leitura e o parsing do documento, fatiando-o em partes semânticas e enviando os blocos para a base vetorial.
2. **Pesquisador (Agent 2):** Realiza buscas vetoriais no ChromaDB sobre o documento e utiliza caching (Redis) para diminuir latência e custos.
3. **Auditor/Compliance (Agent 3):** Cruza as cláusulas e informações extraídas com regras de negócio e marcos regulatórios (Risk Scoring).
4. **Revisor/Consolidador (Agent 4):** Critica as análises dos agentes anteriores e gera um parecer executivo consolidado em formato estruturado.

## Stack Tecnológica

- **Linguagem:** Python 3.12+
- **Framework Web:** FastAPI (com WebSockets para streaming em tempo real)
- **Orquestração de Agentes:** LangGraph & LangChain
- **Banco Vetorial:** ChromaDB
- **Cache Semântico:** Redis
- **Persistência Relacional:** SQLite (via SQLAlchemy Async) com suporte preparado para PostgreSQL.
- **Frontend:** TailwindCSS, Vanilla JS, Jinja2.

## Funcionalidades Implementadas

- [x] Upload e parsing de documentos (PDF).
- [x] Extração inteligente de texto e indexação via embeddings.
- [x] Pipeline multi-agente assíncrono (Extrator -> Pesquisador -> Auditor -> Revisor).
- [x] WebSocket para feedback visual em tempo real do processamento.
- [x] Caching semântico no Redis para não repetir requisições idênticas à LLM.
- [x] Estrutura relacional para Gestão de Workspaces (Empresas, Usuários e Pastas).
- [x] Dashboard corporativo com visualização detalhada dos riscos e cláusulas mitigatórias.

## Setup Local

### Pré-requisitos
- Python 3.12 ou superior
- Pipenv ou Virtualenv

### Instalação

1. Clone o repositório:
```bash
git clone https://github.com/Matheusg0ulart/Programa-analise-contratos.git
cd Programa-analise-contratos
```

2. Crie um ambiente virtual e instale as dependências:
```bash
python -m venv .venv
source .venv/bin/activate  # No Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure as variáveis de ambiente:
Copie o arquivo de exemplo e edite com suas chaves de API:
```bash
cp .env.example .env
```
*(No mínimo, você precisará configurar `OPENAI_API_KEY` ou a chave do provedor configurado no seu arquivo settings.py).*

4. Execute a aplicação:
```bash
python main.py
```

A aplicação estará disponível em `http://localhost:8000`.

## Estrutura do Projeto

```text
├── main.py                  # Entrypoint principal do servidor
├── src/
│   ├── api/                 # Rotas FastAPI, WebSocket e Core Server
│   ├── agents/              # Lógica de cada Agente (Extrator, Revisor, etc)
│   ├── graph/               # Definição e orquestração do LangGraph
│   ├── services/            # Serviços externos (Redis, Chroma, Embeddings)
│   ├── schemas/             # Modelos Pydantic e SQLAlchemy (Banco de Dados)
│   ├── config/              # Configurações globais e variáveis de ambiente
│   ├── templates/           # Arquivos HTML (Jinja2)
│   └── static/              # Assets estáticos (CSS, JS)
├── tests/                   # Suíte de testes automatizados (Pytest)
├── multiagent.db            # Banco de dados SQLite gerado localmente
└── docker-compose.yml       # Infraestrutura para Postgres e Redis
```

## Como Contribuir

1. Faça um Fork do projeto
2. Crie uma branch para sua Feature (`git checkout -b feature/NovaFeature`)
3. Faça o commit de suas alterações (`git commit -m 'feat: adicionando a NovaFeature'`)
4. Faça o Push para a branch (`git push origin feature/NovaFeature`)
5. Abra um Pull Request

## Licença

Este projeto é desenvolvido para uso corporativo e pesquisa em inteligência artificial. Entre em contato com os administradores do repositório para detalhes sobre o licenciamento e uso comercial.
