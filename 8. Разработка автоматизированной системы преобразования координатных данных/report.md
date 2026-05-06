# Отчет по преобразованию координат

## 1. Общая формула преобразования

$$ \left[\begin{matrix}X\\Y\\Z\end{matrix}\right]_{Б} = (1 + m) \left[\begin{matrix}1 & \omega_{Z} & - \omega_{Y}\\- \omega_{Z} & 1 & \omega_{X}\\\omega_{Y} & - \omega_{X} & 1\end{matrix}\right] \left[\begin{matrix}X\\Y\\Z\end{matrix}\right]_{А} + \left[\begin{matrix}\Delta_{X}\\\Delta_{Y}\\\Delta_{Z}\end{matrix}\right] $$

## 2. Общая формула с подставленными в нее параметрами перехода между системами СК-42 и СК-95

$$ \left[\begin{matrix}X\\Y\\Z\end{matrix}\right]_{СК-95} = (1 + -0.2274) \left[\begin{matrix}1 & -0.134263 & -0.003559\\0.134263 & 1 & -0.001738\\0.003559 & 0.001738 & 1\end{matrix}\right] \left[\begin{matrix}X\\Y\\Z\end{matrix}\right]_{СК-42} + \left[\begin{matrix}24.46\\-130.8\\-81.53\end{matrix}\right] $$

## 3. Пример последовательных преобразований одного набора координат

### Общая формула

$$ \left[\begin{matrix}X\\Y\\Z\end{matrix}\right]_{Б} = (1 + m) \left[\begin{matrix}1 & \omega_{Z} & - \omega_{Y}\\- \omega_{Z} & 1 & \omega_{X}\\\omega_{Y} & - \omega_{X} & 1\end{matrix}\right] \left[\begin{matrix}X\\Y\\Z\end{matrix}\right]_{А} + \left[\begin{matrix}\Delta_{X}\\\Delta_{Y}\\\Delta_{Z}\end{matrix}\right] $$

### Подстановка параметров перехода

$$ \left[\begin{matrix}X\\Y\\Z\end{matrix}\right]_{СК-95} = (1 + -0.2274) \left[\begin{matrix}1 & -0.134263 & -0.003559\\0.134263 & 1 & -0.001738\\0.003559 & 0.001738 & 1\end{matrix}\right] \left[\begin{matrix}X\\Y\\Z\end{matrix}\right]_{СК-42} + \left[\begin{matrix}24.46\\-130.8\\-81.53\end{matrix}\right] $$

### Подстановка начальных координат

$$ \left[\begin{matrix}X\\Y\\Z\end{matrix}\right]_{СК-95} = (1 + -0.2274) \left[\begin{matrix}1 & -0.134263 & -0.003559\\0.134263 & 1 & -0.001738\\0.003559 & 0.001738 & 1\end{matrix}\right] \left[\begin{matrix}961550.612\\622041.842\\576074.683\end{matrix}\right]_{СК-42} + \left[\begin{matrix}24.46\\-130.8\\-81.53\end{matrix}\right] $$

### Вычесленные конечные координаты

$$ \left[\begin{matrix}X\\Y\\Z\end{matrix}\right]_{СК-95} = \left[\begin{matrix}961574.853343391\\621910.900547685\\575993.022000617\end{matrix}\right] $$

## 4. Результаты преобразований

| Исходная X | Исходная Y | Исходная Z | Конечная X | Конечная Y | Конечная Z |
| --- | --- | --- | --- | --- | --- |
| 961550.612 | 622041.842 | 576074.683 | 961574.853 | 621910.901 | 575993.022 |
| 703837.225 | 212805.773 | 837587.614 | 703861.525 | 212674.925 | 837505.894 |
