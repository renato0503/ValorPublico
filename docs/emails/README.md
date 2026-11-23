# E-mails de acesso (Firebase Auth)

## Redefinição de senha

O app já tem o fluxo **“Esqueci minha senha”** na tela de login
(`js/auth.js` → `sendPasswordResetEmail`, com `languageCode = "pt-BR"`).

O **conteúdo** do e-mail é um template do Firebase. A API de Admin **não permite
alterá-lo** (`EMAIL_TEMPLATE_UPDATE_NOT_ALLOWED`) — a troca é manual, uma vez por projeto:

1. Firebase Console → **Authentication** → aba **Templates** → **Redefinição de senha**.
2. Assunto: `Redefinir a senha · ValorPúblico` .
3. Cole o conteúdo de [`reset-password.html`](./reset-password.html) no corpo (modo HTML).
4. Confira o “Nome do remetente” em **Configurações do projeto → Nome público**
   (é o `%APP_NAME%` que aparece no e-mail).
5. Envie um teste para o seu próprio e-mail.

> O remetente padrão é `noreply@<projeto>.firebaseapp.com`. Para usar um domínio próprio
> é preciso configurar SMTP no mesmo painel (não é necessário para o fluxo atual).

**Atenção:** o link de redefinição é gerado pelo Firebase e aponta para a página de ação do
projeto, já em português por causa do `languageCode`.

