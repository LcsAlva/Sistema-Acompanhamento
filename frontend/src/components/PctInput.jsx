// Campo numérico que aceita expressões aritméticas (calculadora embutida).
//
// O usuário pode digitar "100/3" e ao sair do campo (blur/Enter) o valor
// é avaliado para 33,33. Útil para ratear % na previsão/medição sem
// precisar calcular à parte.
//
// VALIDAÇÃO FINANCEIRA:
//   - Valores fora de [min, max] são AUTO-AJUSTADOS ao clamp ao confirmar.
//   - Durante a digitação, o campo fica vermelho quando o valor excede os limites,
//     alertando visualmente antes mesmo do commit.
//   - Mensagem de tooltip explica os limites ao usuário.
//
// Props:
//   value     — número atual (ex.: 33.33), na escala do campo (normalmente 0–100)
//   onCommit  — chamado com o número avaliado ao confirmar (já clampado)
//   min       — mínimo permitido (padrão 0)
//   max       — máximo permitido (padrão 100)
//   disabled, title, placeholder, style — repassados ao <input>

import { useState, useEffect, useRef } from 'react'
import { evalExpr, round2, numToInput, clampPct, isPctInvalid } from '../utils/calc'

const MSG_INVALIDO = 'Percentual deve estar entre 0% e 100%.'

export default function PctInput({
  value,
  onCommit,
  disabled,
  title,
  placeholder,
  style,
  min = 0,
  max = 100,
}) {
  const [text, setText] = useState(numToInput(value))
  const [invalido, setInvalido] = useState(false)
  const focusedRef = useRef(false)

  // Re-sincroniza quando o valor muda por fora (ex.: sugestão de admin local)
  // — só quando o campo NÃO está em foco, para não atrapalhar a digitação.
  useEffect(() => {
    if (!focusedRef.current) {
      setText(numToInput(value))
      setInvalido(false)
    }
  }, [value])

  // Avalia a expressão digitada e verifica se está fora dos limites.
  const checkInvalido = (raw) => {
    const r = evalExpr(raw)
    if (r == null) return false   // expressão em aberto — não marca como erro ainda
    return isPctInvalid(r, min, max)
  }

  const handleChange = (e) => {
    const raw = e.target.value
    setText(raw)
    setInvalido(checkInvalido(raw))
  }

  const commit = () => {
    focusedRef.current = false
    const r = evalExpr(text)
    if (r != null) {
      // AUTO-AJUSTE: clamp ao intervalo permitido
      const v = clampPct(r, min, max)
      onCommit(v)
      setText(numToInput(v))
      setInvalido(false)
    } else {
      // Expressão inválida ou vazia → reverte para o último valor válido
      setText(numToInput(value))
      setInvalido(false)
    }
  }

  // Estilo dinâmico: mescla o estilo externo com a borda de erro
  const mergedStyle = {
    ...style,
    ...(invalido
       {
          border: '1.5px solid #DC2626',
          background: style?.background === 'white' || !style?.background
             '#FEF2F2'
            : style.background,
          color: '#991B1B',
        }
      : {}),
  }

  const tooltipText = invalido
     MSG_INVALIDO
    : (title || `Aceita conta — ex.: 100/3, 50+5. Mín: ${min}%, Máx: ${max}%.`)

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <input
        type="text"
        inputMode="decimal"
        value={text}
        disabled={disabled}
        title={tooltipText}
        placeholder={placeholder}
        onFocus={() => { focusedRef.current = true }}
        onChange={handleChange}
        onBlur={commit}
        onKeyDown={e => {
          if (e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur() }
          if (e.key === 'Escape') {
            setText(numToInput(value))
            setInvalido(false)
            e.currentTarget.blur()
          }
        }}
        style={mergedStyle}
        aria-invalid={invalido}
        aria-describedby={invalido  'pct-error-msg' : undefined}
      />
      {invalido && (
        <span
          id="pct-error-msg"
          role="alert"
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            zIndex: 50,
            background: '#DC2626',
            color: '#fff',
            fontSize: 10,
            padding: '2px 6px',
            borderRadius: '0 0 4px 4px',
            whiteSpace: 'nowrap',
            pointerEvents: 'none',
          }}
        >
          {MSG_INVALIDO}
        </span>
      )}
    </div>
  )
}
