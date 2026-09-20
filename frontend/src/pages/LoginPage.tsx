import logo from '@/assets/logo.svg'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Toaster } from '@/components/ui/sonner'
import { useLogin } from '@/hooks/useLogin'


export function LoginPage({ onAuthenticated }: { onAuthenticated: () => void }) {
  const { onSubmit, submitting, labels } = useLogin(onAuthenticated)

  return (
    <>
      <Toaster position="bottom-left" duration={4000} />
      <main className="login-page">
        <form className="login-card" onSubmit={event => void onSubmit(event)}>
          <img src={logo} alt="" className="login-logo" />
          <div className="login-copy">
            <h1>{labels.title}</h1>
            <p>{labels.description}</p>
          </div>
          <label className="login-field">
            <span>{labels.password}</span>
            <Input name="password" type="password" autoComplete="current-password" autoFocus required />
          </label>
          <Button type="submit" disabled={submitting}>{labels.submit}</Button>
        </form>
      </main>
    </>
  )
}
