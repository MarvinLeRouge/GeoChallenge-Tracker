import { describe, it, expect } from "vitest";
import { useFormValidation } from "@/composables/useFormValidation";
import type { ValidationRule } from "@/composables/useFormValidation";

const required: ValidationRule = {
  validate: (v) => v !== null && v !== "" && v !== undefined,
  message: "Required",
};

const minLength = (n: number): ValidationRule => ({
  validate: (v) => typeof v === "string" && v.length >= n,
  message: `Min ${n} chars`,
});

describe("initialValues", () => {
  it("pre-populates fields from initialValues", () => {
    const { fields } = useFormValidation({ email: "a@b.com" });
    expect(fields.email.value).toBe("a@b.com");
  });

  it("marks pre-populated fields as clean and untouched", () => {
    const { fields } = useFormValidation({ email: "a@b.com" });
    expect(fields.email.isDirty).toBe(false);
    expect(fields.email.isTouched).toBe(false);
  });
});

describe("addField", () => {
  it("creates a field with default state", () => {
    const { fields, addField } = useFormValidation();
    addField("name");
    expect(fields.name.value).toBeNull();
    expect(fields.name.errors).toEqual([]);
    expect(fields.name.isValid).toBe(true);
    expect(fields.name.isDirty).toBe(false);
    expect(fields.name.isTouched).toBe(false);
  });

  it("creates a field with a provided initial value", () => {
    const { fields, addField } = useFormValidation();
    addField("age", 30);
    expect(fields.age.value).toBe(30);
  });
});

describe("setFieldValue", () => {
  it("updates the field value", () => {
    const { fields, addField, setFieldValue } = useFormValidation();
    addField("name");
    setFieldValue("name", "Alice");
    expect(fields.name.value).toBe("Alice");
  });

  it("marks the field as dirty", () => {
    const { fields, addField, setFieldValue } = useFormValidation();
    addField("name");
    setFieldValue("name", "Alice");
    expect(fields.name.isDirty).toBe(true);
  });

  it("auto-creates the field if it does not exist", () => {
    const { fields, setFieldValue } = useFormValidation();
    setFieldValue("newField", "value");
    expect(fields.newField.value).toBe("value");
    expect(fields.newField.isDirty).toBe(true);
  });
});

describe("setFieldTouched", () => {
  it("marks the field as touched", () => {
    const { fields, addField, setFieldTouched } = useFormValidation();
    addField("email");
    setFieldTouched("email");
    expect(fields.email.isTouched).toBe(true);
  });
});

describe("validateField", () => {
  it("returns true and clears errors when all rules pass", async () => {
    const { fields, addField, setFieldValue, validateField } =
      useFormValidation();
    addField("email");
    setFieldValue("email", "test@example.com");
    const valid = await validateField("email", [required]);
    expect(valid).toBe(true);
    expect(fields.email.errors).toEqual([]);
    expect(fields.email.isValid).toBe(true);
  });

  it("returns false and records errors when a rule fails", async () => {
    const { fields, addField, validateField } = useFormValidation();
    addField("email");
    const valid = await validateField("email", [required]);
    expect(valid).toBe(false);
    expect(fields.email.errors).toContain("Required");
    expect(fields.email.isValid).toBe(false);
  });

  it("collects errors from multiple failing rules", async () => {
    const { fields, addField, setFieldValue, validateField } =
      useFormValidation();
    addField("pw");
    setFieldValue("pw", "ab");
    const valid = await validateField("pw", [required, minLength(8)]);
    expect(valid).toBe(false);
    expect(fields.pw.errors).toHaveLength(1);
    expect(fields.pw.errors[0]).toContain("Min 8");
  });

  it("returns true without running rules for a non-existent field", async () => {
    const { validateField } = useFormValidation();
    const valid = await validateField("ghost", [required]);
    expect(valid).toBe(true);
  });

  it("supports async validation rules", async () => {
    const asyncRule: ValidationRule = {
      validate: async (v) => {
        await new Promise((r) => setTimeout(r, 0));
        return v === "valid";
      },
      message: 'Must be "valid"',
    };
    const { fields, addField, setFieldValue, validateField } =
      useFormValidation();
    addField("token");
    setFieldValue("token", "invalid");
    await validateField("token", [asyncRule]);
    expect(fields.token.isValid).toBe(false);
  });
});

describe("validateForm", () => {
  it("returns true when all fields pass", async () => {
    const { addField, setFieldValue, validateForm } = useFormValidation();
    addField("a");
    addField("b");
    setFieldValue("a", "hello");
    setFieldValue("b", "world");
    const valid = await validateForm({ a: [required], b: [required] });
    expect(valid).toBe(true);
  });

  it("returns false when any field fails", async () => {
    const { addField, setFieldValue, validateForm } = useFormValidation();
    addField("a");
    addField("b");
    setFieldValue("a", "hello");
    const valid = await validateForm({ a: [required], b: [required] });
    expect(valid).toBe(false);
  });
});

describe("resetField", () => {
  it("resets the field to its initial value", () => {
    const { fields, resetField } = useFormValidation({ name: "initial" });
    fields.name.value = "changed";
    fields.name.isDirty = true;
    resetField("name");
    expect(fields.name.value).toBe("initial");
    expect(fields.name.isDirty).toBe(false);
    expect(fields.name.isValid).toBe(true);
    expect(fields.name.errors).toEqual([]);
  });

  it("is a no-op for a non-existent field", () => {
    const { resetField } = useFormValidation();
    expect(() => resetField("ghost")).not.toThrow();
  });
});

describe("resetForm", () => {
  it("resets all fields to their initial values", () => {
    const { fields, resetForm } = useFormValidation({ a: "x", b: "y" });
    fields.a.value = "changed";
    fields.b.value = "changed";
    resetForm();
    expect(fields.a.value).toBe("x");
    expect(fields.b.value).toBe("y");
  });
});

describe("isFormValid", () => {
  it("is true when all fields are valid", () => {
    const { isFormValid, addField } = useFormValidation();
    addField("a");
    addField("b");
    expect(isFormValid.value).toBe(true);
  });

  it("is false when any field has errors", async () => {
    const { isFormValid, addField, validateField } = useFormValidation();
    addField("a");
    await validateField("a", [required]);
    expect(isFormValid.value).toBe(false);
  });
});

describe("isFormDirty", () => {
  it("is false initially", () => {
    const { isFormDirty, addField } = useFormValidation();
    addField("a");
    expect(isFormDirty.value).toBe(false);
  });

  it("is true once any field is dirtied", () => {
    const { isFormDirty, addField, setFieldValue } = useFormValidation();
    addField("a");
    setFieldValue("a", "hello");
    expect(isFormDirty.value).toBe(true);
  });
});
