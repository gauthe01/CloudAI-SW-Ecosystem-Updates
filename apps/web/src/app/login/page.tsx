import { LoginForm } from "@/features/auth/LoginForm";
import { productName } from "@/lib/product";

export default function LoginPage() {
  return (
    <main className="login-page">
      <section className="login-brand-panel" aria-label={productName}>
        <div className="login-brand-content">
          <h1>{productName}</h1>
        </div>
      </section>

      <section className="login-form-panel" aria-labelledby="login-title">
        <div className="login-card">
          <h2 id="login-title">Sign in</h2>
          <p className="login-support">Use your ARM username or email ID to continue.</p>
          <LoginForm />
        </div>
      </section>
    </main>
  );
}
