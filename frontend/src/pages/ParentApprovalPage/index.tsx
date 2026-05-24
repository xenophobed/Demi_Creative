import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, CircleAlert, Loader2 } from "lucide-react";
import Card from "@/components/common/Card";
import { authService } from "@/api/services/authService";
import { getErrorMessage } from "@/api/client";

type ApprovalState =
  | { status: "loading" }
  | { status: "approved" }
  | { status: "error"; message: string };

export default function ParentApprovalPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const [state, setState] = useState<ApprovalState>({ status: "loading" });

  useEffect(() => {
    if (!token) {
      setState({ status: "error", message: "Approval link is missing a token." });
      return;
    }

    let cancelled = false;
    authService
      .approveParentApprovalToken(token)
      .then(() => {
        if (!cancelled) setState({ status: "approved" });
      })
      .catch((err) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: getErrorMessage(err),
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="min-h-screen gradient-bg flex items-center justify-center p-4">
      <Card variant="elevated" padding="lg" className="w-full max-w-md bg-white/95 text-center">
        {state.status === "loading" && (
          <div className="space-y-4 py-4">
            <Loader2 className="mx-auto h-10 w-10 animate-spin text-primary" />
            <h1 className="text-xl font-bold text-gray-800">Checking approval link</h1>
            <p className="text-sm text-gray-500">
              This will only take a moment.
            </p>
          </div>
        )}

        {state.status === "approved" && (
          <div className="space-y-4 py-4">
            <CheckCircle2 className="mx-auto h-12 w-12 text-green-500" />
            <h1 className="text-xl font-bold text-gray-800">Approved</h1>
            <p className="text-sm text-gray-500">
              The child account can now continue with parent-approved features.
            </p>
            <Link className="inline-flex text-sm font-semibold text-primary" to="/login">
              Back to sign in
            </Link>
          </div>
        )}

        {state.status === "error" && (
          <div className="space-y-4 py-4">
            <CircleAlert className="mx-auto h-12 w-12 text-amber-500" />
            <h1 className="text-xl font-bold text-gray-800">Approval link did not work</h1>
            <p className="text-sm text-gray-500">{state.message}</p>
            <Link className="inline-flex text-sm font-semibold text-primary" to="/login">
              Back to sign in
            </Link>
          </div>
        )}
      </Card>
    </div>
  );
}
