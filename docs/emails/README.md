# E-mails de acesso — ValorPúblico

Templates finais dos três e-mails de autenticação do Firebase, já no visual do painel.

| Template | Assunto | Arquivo |
|---|---|---|
| Verificação de e-mail | `Ative seu acesso · ValorPúblico` | `verify-email.html` |
| Redefinição de senha | `Redefinir a senha · ValorPúblico` | `reset-password.html` |
| Alteração de e-mail | `Seu e-mail de acesso foi alterado · ValorPúblico` | `change-email.html` |

Abra `preview.html` para ver as prévias, copiar o HTML ou abrir cada arquivo.

## Aplicar no Firebase

Com a service account em `backend/serviceAccountKey.json`:

```powershell
python docs/emails/aplicar_templates.py --dry-run
python docs/emails/aplicar_templates.py
python docs/emails/aplicar_templates.py --check
```

Para aplicar só um modelo:

```powershell
python docs/emails/aplicar_templates.py --only resetPasswordTemplate
```


> Situação em 25/11/2026: os dois projetos retornaram `EMAIL_TEMPLATE_UPDATE_NOT_ALLOWED` no PATCH. O conteúdo está pronto; a publicação depende do Console ou de liberação do Firebase Support.

O script usa a Identity Toolkit Admin API (`identitytoolkit.googleapis.com/admin/v2/projects/valorpublico-b1e6d/config`) e envia `subject`, `body`, `bodyFormat=HTML` e `senderDisplayName`. O endereço de ação existente (`callbackUri`) não é alterado.

Se a API retornar `EMAIL_TEMPLATE_UPDATE_NOT_ALLOWED`, o projeto está sob a restrição do Firebase: os arquivos continuam prontos e podem ser colados em **Firebase Console → Authentication → Templates**. Nesse caso, use o assunto da tabela e o HTML do arquivo correspondente.

## Placeholders

- `%EMAIL%`: endereço da conta que recebe o e-mail.
- `%NEW_EMAIL%`: novo endereço, usado no aviso de alteração.
- `%LINK%`: link de ação gerado pelo Firebase.
- `%DISPLAY_NAME%`: não é necessário nestes modelos.

Não use `%APP_NAME%` nos textos: o nome público do projeto pode aparecer como o ID técnico. O nome da marca está escrito no HTML.

## Observação sobre alteração de e-mail

O template `changeEmailTemplate` do Firebase é um **aviso de segurança com link para desfazer a alteração**, não uma confirmação do novo endereço. Por isso o botão se chama **Desfazer alteração**.


