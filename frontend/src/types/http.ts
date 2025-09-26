export type FastAPIValidationItem = {
    loc?: Array<string | number>
    msg?: string
    type?: string
}

export type FastAPIErrorBody = {
    detail?: string | FastAPIValidationItem[]
    msg?: string
}

export type FastAPIErrorDetail = string | FastAPIValidationItem[] | undefined
