def test():
    yield 1
    yield 2
    yield 3

# 创建生成器
g = test()

# 每次调用，只走到下一个 yield，然后停住
print(next(g))  # 1
print(next(g))  # 2
print(next(g))  # 3