import { describe, it, expect, vi, beforeEach } from "vitest";

const mockGet = vi.hoisted(() => vi.fn());
const mockPut = vi.hoisted(() => vi.fn());

vi.mock("@/api/http", () => ({ default: { get: mockGet, put: mockPut } }));
vi.mock("@/composables/useApiErrorHandler", () => ({
  useApiErrorHandler: () => ({
    handleApiError: vi.fn().mockReturnValue({ message: "API error" }),
  }),
}));

import { useUserProfile } from "@/composables/useUserProfile";
import type { UserLocationOut, UserProfileOut } from "@/types/index";

const makeProfile = (): UserProfileOut =>
  ({
    id: "u1",
    username: "testuser",
    email: "test@example.com",
    location: null,
  }) as unknown as UserProfileOut;

const makeLocation = (
  overrides: Partial<UserLocationOut> = {},
): UserLocationOut =>
  ({
    lat: 48.8566,
    lon: 2.3522,
    coords: null,
    ...overrides,
  }) as unknown as UserLocationOut;

beforeEach(() => vi.clearAllMocks());

describe("hasLocation", () => {
  it("is falsy when location is null", () => {
    const { hasLocation } = useUserProfile();
    expect(hasLocation.value).toBeFalsy();
  });

  it("is truthy when lat and lon are set", () => {
    const { location, hasLocation } = useUserProfile();
    location.value = makeLocation();
    expect(hasLocation.value).toBeTruthy();
  });

  it("is falsy when lat is null", () => {
    const { location, hasLocation } = useUserProfile();
    location.value = makeLocation({ lat: null as unknown as number });
    expect(hasLocation.value).toBeFalsy();
  });
});

describe("locationString", () => {
  it("returns null when location is absent", () => {
    const { locationString } = useUserProfile();
    expect(locationString.value).toBeNull();
  });

  it("formats coords string from backend format", () => {
    const { location, locationString } = useUserProfile();
    location.value = makeLocation({ coords: "N43 06.628 E5 56.557" });
    expect(locationString.value).toBe("N 43° 06.628′ E 5° 56.557′");
  });

  it("falls back to decimal format when coords is absent", () => {
    const { location, locationString } = useUserProfile();
    location.value = makeLocation({ coords: null, lat: 48.8566, lon: 2.3522 });
    expect(locationString.value).toBe("48.856600, 2.352200");
  });
});

describe("loadProfile", () => {
  it("sets profile and location on success", async () => {
    const loc = makeLocation();
    mockGet
      .mockResolvedValueOnce({ data: makeProfile() })
      .mockResolvedValueOnce({ data: loc });
    const { profile, location, loadProfile } = useUserProfile();

    await loadProfile();

    expect(profile.value).not.toBeNull();
    expect(location.value).toEqual(loc);
  });

  it("sets location to null when response data is null", async () => {
    mockGet
      .mockResolvedValueOnce({ data: makeProfile() })
      .mockResolvedValueOnce({ data: null });
    const { location, loadProfile } = useUserProfile();

    await loadProfile();

    expect(location.value).toBeNull();
  });

  it("sets location to null when lat/lon are null", async () => {
    mockGet
      .mockResolvedValueOnce({ data: makeProfile() })
      .mockResolvedValueOnce({ data: { lat: null, lon: null } });
    const { location, loadProfile } = useUserProfile();

    await loadProfile();

    expect(location.value).toBeNull();
  });

  it("sets error on failure", async () => {
    mockGet.mockRejectedValueOnce(new Error("fail"));
    const { error, loadProfile } = useUserProfile();

    await loadProfile();

    expect(error.value).toBe("API error");
  });

  it("resets loading to false after call", async () => {
    mockGet
      .mockResolvedValueOnce({ data: makeProfile() })
      .mockResolvedValueOnce({ data: null });
    const { loading, loadProfile } = useUserProfile();

    await loadProfile();
    expect(loading.value).toBe(false);
  });
});

describe("loadLocation", () => {
  it("sets location on success", async () => {
    const loc = makeLocation();
    mockGet.mockResolvedValueOnce({ data: loc });
    const { location, loadLocation } = useUserProfile();

    await loadLocation();

    expect(location.value).toEqual(loc);
  });

  it("sets error on failure", async () => {
    mockGet.mockRejectedValueOnce(new Error("fail"));
    const { error, loadLocation } = useUserProfile();

    await loadLocation();

    expect(error.value).toBe("API error");
  });
});

describe("updateProfile", () => {
  it("updates profile and returns data on success", async () => {
    const updated = makeProfile();
    mockPut.mockResolvedValueOnce({ data: updated });
    const { profile, updateProfile } = useUserProfile();

    const result = await updateProfile({ username: "newname" });

    expect(profile.value).toEqual(updated);
    expect(result).toEqual(updated);
  });

  it("sets saveError and re-throws on failure", async () => {
    mockPut.mockRejectedValueOnce(new Error("fail"));
    const { saveError, updateProfile } = useUserProfile();

    await expect(updateProfile({})).rejects.toThrow();
    expect(saveError.value).toBe("API error");
  });

  it("resets saving to false after call", async () => {
    mockPut.mockResolvedValueOnce({ data: makeProfile() });
    const { saving, updateProfile } = useUserProfile();

    await updateProfile({});
    expect(saving.value).toBe(false);
  });
});

describe("updateLocation", () => {
  it("refreshes location from GET after PUT", async () => {
    const loc = makeLocation({ lat: 10, lon: 20 });
    mockPut.mockResolvedValueOnce({});
    mockGet.mockResolvedValueOnce({ data: loc });
    const { location, updateLocation } = useUserProfile();

    await updateLocation({ lat: 10, lon: 20 } as never);

    expect(location.value).toEqual(loc);
  });

  it("also updates profile.location when profile is loaded", async () => {
    const loc = makeLocation();
    mockPut.mockResolvedValueOnce({});
    mockGet.mockResolvedValueOnce({ data: loc });
    const { profile, updateLocation } = useUserProfile();
    profile.value = makeProfile();

    await updateLocation({ lat: 48, lon: 2 } as never);

    expect(profile.value?.location).toEqual(loc);
  });

  it("sets saveError and re-throws on failure", async () => {
    mockPut.mockRejectedValueOnce(new Error("fail"));
    const { saveError, updateLocation } = useUserProfile();

    await expect(updateLocation({} as never)).rejects.toThrow();
    expect(saveError.value).toBe("API error");
  });
});
