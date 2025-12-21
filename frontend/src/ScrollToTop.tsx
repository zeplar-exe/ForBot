import { useEffect } from "react"
import { useLocation } from "react-router-dom"

/**
 * ScrollToTop - resets window scroll to top on route change.
 * Place once inside your Router (App is already wrapped in BrowserRouter).
 */
export default function ScrollToTop() {
  const { pathname } = useLocation()

  useEffect(() => {
    try {
      window.scrollTo({ top: 0, left: 0, behavior: "auto" })
    } catch {
      // fallback for older browsers/environments
      window.scrollTo(0, 0)
    }
  }, [pathname])

  return null
}
