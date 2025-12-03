// src/composables/useFormValidation.ts
import { ref, reactive, computed } from 'vue';

export interface ValidationRule {
  validate: (value: any) => boolean | Promise<boolean>;
  message: string;
}

export interface FieldState {
  value: any;
  errors: string[];
  isValid: boolean;
  isDirty: boolean;
  isTouched: boolean;
}

export function useFormValidation(initialValues: Record<string, any> = {}) {
  const fields = reactive<Record<string, FieldState>>({});
  
  // Initialize fields with initial values
  Object.entries(initialValues).forEach(([name, value]) => {
    fields[name] = {
      value,
      errors: [],
      isValid: true,
      isDirty: false,
      isTouched: false
    };
  });

  const addField = (name: string, initialValue: any = null) => {
    fields[name] = {
      value: initialValue,
      errors: [],
      isValid: true,
      isDirty: false,
      isTouched: false
    };
  };

  const setFieldValue = (name: string, value: any) => {
    if (!fields[name]) {
      addField(name, value);
    }
    fields[name].value = value;
    fields[name].isDirty = true;
  };

  const setFieldTouched = (name: string) => {
    fields[name].isTouched = true;
  };

  const validateField = async (name: string, rules: ValidationRule[]) => {
    if (!fields[name]) return true;

    const field = fields[name];
    const errors: string[] = [];

    for (const rule of rules) {
      const isValid = await Promise.resolve(rule.validate(field.value));
      if (!isValid) {
        errors.push(rule.message);
      }
    }

    field.errors = errors;
    field.isValid = errors.length === 0;
    return field.isValid;
  };

  const validateForm = async (fieldRules: Record<string, ValidationRule[]>) => {
    let isFormValid = true;
    
    for (const fieldName in fieldRules) {
      const isValid = await validateField(fieldName, fieldRules[fieldName]);
      if (!isValid) {
        isFormValid = false;
      }
    }

    return isFormValid;
  };

  const resetField = (name: string) => {
    if (fields[name]) {
      fields[name].value = initialValues[name] || null;
      fields[name].errors = [];
      fields[name].isValid = true;
      fields[name].isDirty = false;
      fields[name].isTouched = false;
    }
  };

  const resetForm = () => {
    Object.keys(fields).forEach(key => {
      fields[key].value = initialValues[key] || null;
      fields[key].errors = [];
      fields[key].isValid = true;
      fields[key].isDirty = false;
      fields[key].isTouched = false;
    });
  };

  const isFormValid = computed(() => {
    return Object.values(fields).every(field => field.isValid);
  });

  const isFormDirty = computed(() => {
    return Object.values(fields).some(field => field.isDirty);
  });

  return {
    fields,
    addField,
    setFieldValue,
    setFieldTouched,
    validateField,
    validateForm,
    resetField,
    resetForm,
    isFormValid,
    isFormDirty
  };
}