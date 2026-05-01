"""
快速排序算法实现
时间复杂度：平均O(n log n)，最坏O(n²)
空间复杂度：平均O(log n)，最坏O(n)
"""

def quicksort(arr):
    """
    快速排序主函数
    
    Args:
        arr: 待排序的列表
        
    Returns:
        排序后的列表
    """
    # 基本情况：空列表或只有一个元素
    if len(arr) <= 1:
        return arr
    
    # 选择基准元素（这里选择中间元素）
    pivot = arr[len(arr) // 2]
    
    # 分区操作
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    
    # 递归排序并合并
    return quicksort(left) + middle + quicksort(right)


def quicksort_inplace(arr, low=0, high=None):
    """
    原地快速排序（节省内存）
    
    Args:
        arr: 待排序的列表（会被修改）
        low: 起始索引
        high: 结束索引
        
    Returns:
        None（原地排序）
    """
    if high is None:
        high = len(arr) - 1
    
    if low < high:
        # 分区并获取基准位置
        pivot_index = partition(arr, low, high)
        
        # 递归排序左右两部分
        quicksort_inplace(arr, low, pivot_index - 1)
        quicksort_inplace(arr, pivot_index + 1, high)


def partition(arr, low, high):
    """
    分区函数（Lomuto分区方案）
    
    Args:
        arr: 待分区的列表
        low: 起始索引
        high: 结束索引
        
    Returns:
        基准元素的最终位置
    """
    # 选择最后一个元素作为基准
    pivot = arr[high]
    
    # i指向小于基准的区域的边界
    i = low - 1
    
    for j in range(low, high):
        if arr[j] <= pivot:
            i += 1
            # 交换元素
            arr[i], arr[j] = arr[j], arr[i]
    
    # 将基准放到正确位置
    arr[i + 1], arr[high] = arr[high], arr[i + 1]
    return i + 1


def quicksort_hoare(arr, low=0, high=None):
    """
    使用Hoare分区方案的快速排序
    
    Args:
        arr: 待排序的列表
        low: 起始索引
        high: 结束索引
        
    Returns:
        None（原地排序）
    """
    if high is None:
        high = len(arr) - 1
    
    if low < high:
        # Hoare分区
        pivot_index = partition_hoare(arr, low, high)
        
        # 递归排序
        quicksort_hoare(arr, low, pivot_index)
        quicksort_hoare(arr, pivot_index + 1, high)


def partition_hoare(arr, low, high):
    """
    Hoare分区方案
    
    Args:
        arr: 待分区的列表
        low: 起始索引
        high: 结束索引
        
    Returns:
        基准元素的最终位置
    """
    # 选择中间元素作为基准
    pivot = arr[(low + high) // 2]
    
    i = low - 1
    j = high + 1
    
    while True:
        # 从左向右找到第一个大于等于基准的元素
        i += 1
        while arr[i] < pivot:
            i += 1
        
        # 从右向左找到第一个小于等于基准的元素
        j -= 1
        while arr[j] > pivot:
            j -= 1
        
        # 如果指针相遇或交叉，返回j
        if i >= j:
            return j
        
        # 交换元素
        arr[i], arr[j] = arr[j], arr[i]


def test_quicksort():
    """测试函数"""
    print("=== 快速排序算法测试 ===")
    
    # 测试数据
    test_cases = [
        [64, 34, 25, 12, 22, 11, 90],
        [5, 2, 8, 1, 9],
        [1],
        [],
        [3, 3, 3, 3],
        [9, 8, 7, 6, 5, 4, 3, 2, 1]
    ]
    
    for i, test_arr in enumerate(test_cases):
        print(f"\n测试用例 {i+1}: {test_arr}")
        
        # 方法1：简单快速排序
        arr1 = test_arr.copy()
        sorted1 = quicksort(arr1)
        print(f"  简单快速排序: {sorted1}")
        
        # 方法2：原地快速排序
        arr2 = test_arr.copy()
        quicksort_inplace(arr2)
        print(f"  原地快速排序: {arr2}")
        
        # 方法3：Hoare分区快速排序
        arr3 = test_arr.copy()
        quicksort_hoare(arr3)
        print(f"  Hoare快速排序: {arr3}")
        
        # 验证排序正确性
        assert sorted1 == sorted(test_arr), f"简单快速排序错误: {test_arr}"
        assert arr2 == sorted(test_arr), f"原地快速排序错误: {test_arr}"
        assert arr3 == sorted(test_arr), f"Hoare快速排序错误: {test_arr}"
    
    print("\n✅ 所有测试通过！")


def benchmark_quicksort():
    """性能基准测试"""
    import random
    import time
    
    print("\n=== 性能基准测试 ===")
    
    # 生成测试数据
    sizes = [100, 1000, 10000]
    
    for size in sizes:
        print(f"\n数据规模: {size} 个元素")
        arr = [random.randint(0, 10000) for _ in range(size)]
        
        # 测试简单快速排序
        start = time.time()
        quicksort(arr.copy())
        simple_time = time.time() - start
        
        # 测试原地快速排序
        start = time.time()
        arr_copy = arr.copy()
        quicksort_inplace(arr_copy)
        inplace_time = time.time() - start
        
        # 测试Hoare快速排序
        start = time.time()
        arr_copy = arr.copy()
        quicksort_hoare(arr_copy)
        hoare_time = time.time() - start
        
        print(f"  简单快速排序: {simple_time:.6f} 秒")
        print(f"  原地快速排序: {inplace_time:.6f} 秒")
        print(f"  Hoare快速排序: {hoare_time:.6f} 秒")


if __name__ == "__main__":
    # 运行测试
    test_quicksort()
    
    # 运行性能测试（小规模）
    benchmark_quicksort()
    
    print("\n=== 使用示例 ===")
    example_arr = [3, 6, 8, 10, 1, 2, 1]
    print(f"原始数组: {example_arr}")
    
    # 使用简单版本
    sorted_arr = quicksort(example_arr)
    print(f"排序后: {sorted_arr}")
    
    # 使用原地版本
    arr_copy = example_arr.copy()
    quicksort_inplace(arr_copy)
    print(f"原地排序: {arr_copy}")