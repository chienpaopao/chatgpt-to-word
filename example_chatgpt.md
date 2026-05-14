# 數學筆記：微積分基礎

## 極限定義

函數 $f(x)$ 在 $x = a$ 的極限定義如下：

$$\lim_{x \to a} f(x) = L$$

若對任意 $\varepsilon > 0$，存在 $\delta > 0$ 使得 $0 < |x - a| < \delta \Rightarrow |f(x) - L| < \varepsilon$。

## 導數

函數的導數定義為：

$$f'(x) = \lim_{h \to 0} \frac{f(x+h) - f(x)}{h}$$

### 常用公式

| 函數 | 導數 |
|------|------|
| $x^n$ | $nx^{n-1}$ |
| $e^x$ | $e^x$ |
| $\ln x$ | $\dfrac{1}{x}$ |
| $\sin x$ | $\cos x$ |

## 積分基本定理

若 $F'(x) = f(x)$，則：

$$\int_a^b f(x)\,dx = F(b) - F(a)$$

### 範例計算

計算 $\displaystyle\int_0^1 x^2\,dx$：

$$\int_0^1 x^2\,dx = \left[\frac{x^3}{3}\right]_0^1 = \frac{1}{3}$$

## 泰勒展開

$$e^x = \sum_{n=0}^{\infty} \frac{x^n}{n!} = 1 + x + \frac{x^2}{2!} + \frac{x^3}{3!} + \cdots$$
