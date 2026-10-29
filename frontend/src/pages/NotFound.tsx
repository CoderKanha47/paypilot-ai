import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <p className="text-6xl font-semibold text-slate-200">404</p>
      <h1 className="mt-3 text-xl font-semibold">Page not found</h1>
      <p className="mt-1 text-sm text-slate-500">That route does not exist in PayPilot AI.</p>
      <Link to="/" className="btn btn-primary mt-5">Back to overview</Link>
    </div>
  );
}