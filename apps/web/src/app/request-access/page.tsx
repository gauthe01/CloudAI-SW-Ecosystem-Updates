import { RequestAccessForm } from "@/features/auth/RequestAccessForm";
import { productName } from "@/lib/product";

export default function RequestAccessPage() {
  return (
    <main className="login-page">
      <section className="login-brand-panel" aria-label={productName}>
        <div className="login-brand-content">
          <h1>{productName}</h1>
        </div>
      </section>

      <section className="login-form-panel" aria-labelledby="request-access-title">
        <div className="login-card">
          <h2 id="request-access-title">Request access</h2>
          <p className="login-support">Use your ARM email ID to request local pilot access.</p>
          <RequestAccessForm />
        </div>
      </section>
    </main>
  );
}
