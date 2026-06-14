/* @vitest-environment node */

import { describe, expect, it } from "vitest";
import { AxiosError } from "axios";

import { getErrorMessage } from "./client";

describe("getErrorMessage", () => {
  it("surfaces the first backend validation detail", () => {
    const error = new AxiosError(
      "Request failed with status code 422",
      "ERR_BAD_REQUEST",
      undefined,
      undefined,
      {
        status: 422,
        statusText: "Unprocessable Entity",
        headers: {},
        config: {} as never,
        data: {
          error: "ValidationError",
          message: "Request parameter validation failed",
          details: [
            {
              field: "body.username",
              message:
                "Value error, Username can only contain letters, numbers, underscores, and hyphens",
              code: "value_error",
            },
          ],
          timestamp: "2026-06-14T00:00:00",
        },
      },
    );

    expect(getErrorMessage(error)).toContain("Username can only contain");
  });
});
