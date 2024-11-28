# Procedimento Operacional Padrão para Backup do Banco de Dados PostgreSQL e Envio de Chaves

Para migração do serviço PEC APS para outra infraestrutura, é necessário alguns recursos para garantir o total funcionamento do prontuário e suas integrações com serviços externos com segurança.

## 1. Realizando o Backup (Dump) do Banco de Dados PostgreSQL

### Linux
1. Execute o comando para criar um dump em formato **plain**:
   ```bash
   pg_dump -U <usuario> -d <nome_do_banco> -F p > backup.sql
   ```

2. Compacte o arquivo:
   - **ZIP**:
     ```bash
     zip backup.zip backup.sql
     ```
   - **TAR.GZ**:
     ```bash
     tar -czvf backup.tar.gz backup.sql
     ```

### Windows
1. No PowerShell, crie o dump em formato **plain**:
   ```powershell
   pg_dump -U <usuario> -d <nome_do_banco> -F p > backup.sql
   ```

2. Compacte o arquivo:
   - **ZIP**:
     ```powershell
     Compress-Archive -Path backup.sql -DestinationPath backup.zip
     ```

## 2. Envio do Backup para Google Drive (ou Alternativas)
1. Faça o upload do arquivo compactado para o Google Drive (ou outro serviço de nuvem, como Dropbox ou OneDrive).
2. Gere o link de compartilhamento e envie-o ao destinatário.

## 3. Envio das Chaves Necessárias

### Contra-Chave para Instalação do PEC e Agendamento Online
Para envio e instalação da contra-chave do PEC, siga o manual oficial: [Criando Contra-Chave](https://saps-ms.github.io/Manual-eSUS_APS/docs/PEC/PEC_02_instalacao/#244-gerar-contra-chave-e-ativar-agendamento-online).

### Chave para Acesso à RNDS
Siga as instruções para garantir a configuração correta para acessar a RNDS conforme descrito no manual: [Configuração de Acesso à RNDS](https://saps-ms.github.io/Manual-eSUS_APS/docs/PEC/PEC_03_adm_conf/#312-acessando-a-rnds-por-meio-do-pec).

## 4. Certificados HTTPS
Caso a unidade tenha adquirido um certificado HTTPS, compartilhe-o seguindo o tipo:
- **Certificados comprados**: Como SSL DV (Domain Validation), OV (Organization Validation) ou EV (Extended Validation) são recomendados para autenticação segura.
- **Certificados autoassinados ou Certbot**: Podem ser utilizados, mas possuem limitações de confiança em navegadores e aplicativos.

Envie o arquivo do certificado (`.pfx` ou `.crt`) junto com as credenciais de instalação, caso aplicável.
